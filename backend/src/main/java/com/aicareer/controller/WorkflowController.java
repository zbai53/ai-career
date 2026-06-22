package com.aicareer.controller;

import com.aicareer.mapper.JobDescriptionMapper;
import com.aicareer.mapper.MatchResultMapper;
import com.aicareer.mapper.ResumeMapper;
import com.aicareer.mapper.RewriteResultMapper;
import com.aicareer.model.entity.JobDescription;
import com.aicareer.model.entity.MatchResultEntity;
import com.aicareer.model.entity.Resume;
import com.aicareer.model.entity.RewriteResultEntity;
import com.aicareer.service.AgentRunService;
import com.aicareer.service.AgentServiceClient;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/workflow")
public class WorkflowController {

    private static final Logger log = LoggerFactory.getLogger(WorkflowController.class);
    // Placeholder until real auth is wired in
    private static final long HARDCODED_USER_ID = 1L;

    private final ResumeMapper resumeMapper;
    private final JobDescriptionMapper jobDescriptionMapper;
    private final MatchResultMapper matchResultMapper;
    private final RewriteResultMapper rewriteResultMapper;
    private final AgentServiceClient agentServiceClient;
    private final AgentRunService agentRunService;
    private final ObjectMapper objectMapper;

    public WorkflowController(ResumeMapper resumeMapper,
                              JobDescriptionMapper jobDescriptionMapper,
                              MatchResultMapper matchResultMapper,
                              RewriteResultMapper rewriteResultMapper,
                              AgentServiceClient agentServiceClient,
                              AgentRunService agentRunService,
                              ObjectMapper objectMapper) {
        this.resumeMapper = resumeMapper;
        this.jobDescriptionMapper = jobDescriptionMapper;
        this.matchResultMapper = matchResultMapper;
        this.rewriteResultMapper = rewriteResultMapper;
        this.agentServiceClient = agentServiceClient;
        this.agentRunService = agentRunService;
        this.objectMapper = objectMapper;
    }

    /**
     * Runs the full LangGraph workflow for a given resume + JD pair.
     *
     * <p>Loads both records from the database, constructs a thread_id scoped to
     * the user, calls the agent-service workflow endpoint, persists every
     * agent_run entry from the returned state, and returns the full workflow
     * state (including match_result and agent_runs) to the caller.
     *
     * <p>The workflow internally chains ResumeAgent → JDAgent → MatchAgent; the
     * Spring Boot layer passes the stored file path and raw JD text rather than
     * re-uploading file bytes.
     */
    @PostMapping("/run")
    public ResponseEntity<Object> runWorkflow(@RequestBody WorkflowRunRequest request) {
        Resume resume = resumeMapper.findById(request.resumeId());
        if (resume == null) {
            return ResponseEntity.notFound().build();
        }

        JobDescription jd = jobDescriptionMapper.findById(request.jdId());
        if (jd == null) {
            return ResponseEntity.notFound().build();
        }

        // Build a stable thread_id so the same user+pair can be resumed.
        String threadId = "user-" + HARDCODED_USER_ID
                + "-resume-" + request.resumeId()
                + "-jd-" + request.jdId();

        long startMs = System.currentTimeMillis();
        log.info("Workflow run — resumeId={} jdId={} threadId={}", request.resumeId(), request.jdId(), threadId);

        try {
            String workflowJson = agentServiceClient.runWorkflow(
                    resume.getFilePath(),
                    jd.getRawText(),
                    String.valueOf(HARDCODED_USER_ID),
                    threadId
            );

            JsonNode root = objectMapper.readTree(workflowJson);

            // Persist every agent_run entry accumulated during the workflow.
            // The workflow state holds a list under "agent_runs"; we wrap each
            // element in {"agent_run": ...} to match the shape that saveFromResponse expects.
            JsonNode agentRunsNode = root.get("agent_runs");
            if (agentRunsNode != null && agentRunsNode.isArray()) {
                for (JsonNode runNode : agentRunsNode) {
                    try {
                        String wrapped = objectMapper.writeValueAsString(
                                Map.of("agent_run", runNode));
                        agentRunService.saveFromResponse(wrapped, HARDCODED_USER_ID);
                    } catch (Exception logEx) {
                        log.warn("Failed to persist one agent_run entry from workflow (threadId={}): {}",
                                threadId, logEx.getMessage());
                    }
                }
            }

            long elapsedMs = System.currentTimeMillis() - startMs;
            log.info("Workflow complete — threadId={} elapsed={}ms", threadId, elapsedMs);

            return ResponseEntity.ok(root);

        } catch (Exception e) {
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.error("Workflow failed after {}ms — threadId={}: {}", elapsedMs, threadId, e.getMessage());
            return ResponseEntity.internalServerError().body(
                    Map.of("error", "Workflow failed: " + e.getMessage()));
        }
    }

    /**
     * Proxies a workflow status check to the agent-service.
     *
     * <p>Returns the current checkpoint state for the given thread_id:
     * current_step, next pending nodes, is_complete, match_result, and
     * the count of agent_runs logged so far.
     */
    @GetMapping("/status/{threadId}")
    public ResponseEntity<Object> getWorkflowStatus(@PathVariable String threadId) {
        try {
            String statusJson = agentServiceClient.getWorkflowStatus(threadId);
            JsonNode root = objectMapper.readTree(statusJson);
            return ResponseEntity.ok(root);
        } catch (Exception e) {
            log.warn("Workflow status check failed for threadId={}: {}", threadId, e.getMessage());
            return ResponseEntity.internalServerError().body(
                    Map.of("error", "Status check failed: " + e.getMessage()));
        }
    }

    /**
     * Spring Boot-orchestrated full workflow: match → optional rewrite → persist.
     *
     * <p>This is the Spring Boot-controlled alternative to the Python
     * {@code POST /api/pipeline/run}. Both paths produce the same result, but
     * this version gives Spring Boot direct control over persistence order and
     * lets callers retrieve results via {@code GET /api/workflow/full/{id}}.
     *
     * <ol>
     *   <li>Load resume and JD from the database by their IDs.</li>
     *   <li>Call Python {@code POST /api/match} to score the pair.</li>
     *   <li>Persist the match result to {@code match_results}.</li>
     *   <li>If {@code overall_score < 70}, call Python {@code POST /api/rewrite}
     *       and persist the rewrite result to {@code rewrite_results}.</li>
     *   <li>Persist all {@code agent_run} entries from both calls.</li>
     *   <li>Return a combined response containing scores, gap analysis, and the
     *       rewrite result (when applicable).</li>
     * </ol>
     */
    @PostMapping("/full")
    public ResponseEntity<Object> runFullWorkflow(@RequestBody FullWorkflowRequest request) {
        Resume resume = resumeMapper.findById(request.resumeId());
        if (resume == null) {
            return ResponseEntity.notFound().build();
        }

        JobDescription jd = jobDescriptionMapper.findById(request.jdId());
        if (jd == null) {
            return ResponseEntity.notFound().build();
        }

        long startMs = System.currentTimeMillis();
        log.info("Full workflow — resumeId={} jdId={}", request.resumeId(), request.jdId());

        try {
            // ── Step 1: match ────────────────────────────────────────────────
            String matchJson = agentServiceClient.matchResumeToJD(
                    resume.getParsedData(), jd.getParsedData());

            JsonNode matchRoot = objectMapper.readTree(matchJson);

            MatchResultEntity matchEntity = new MatchResultEntity();
            matchEntity.setUserId(HARDCODED_USER_ID);
            matchEntity.setResumeId(request.resumeId());
            matchEntity.setJdId(request.jdId());
            matchEntity.setOverallScore(decimalField(matchRoot, "overall_score"));
            matchEntity.setSkillScore(decimalField(matchRoot, "skill_score"));
            matchEntity.setExperienceScore(decimalField(matchRoot, "experience_score"));
            matchEntity.setKeywordScore(decimalField(matchRoot, "keyword_score"));
            matchEntity.setGapAnalysis(matchJson);
            matchResultMapper.insert(matchEntity);

            log.info("Match saved (id={}) overall={}", matchEntity.getId(), matchEntity.getOverallScore());

            // Persist the match agent_run
            try {
                agentRunService.saveFromResponse(matchJson, HARDCODED_USER_ID);
            } catch (Exception logEx) {
                log.warn("Failed to persist match agent_run (resumeId={} jdId={}): {}",
                        request.resumeId(), request.jdId(), logEx.getMessage());
            }

            // ── Step 2: conditional rewrite ──────────────────────────────────
            double overallScore = matchRoot.path("overall_score").asDouble(0.0);
            JsonNode rewriteRoot = null;
            RewriteResultEntity rewriteEntity = null;

            if (overallScore < 70.0) {
                log.info("overall_score={} < 70 — triggering rewrite for resumeId={} jdId={}",
                        overallScore, request.resumeId(), request.jdId());

                String rewriteJson = agentServiceClient.rewriteResume(
                        resume.getParsedData(), jd.getParsedData(), matchJson);

                rewriteRoot = objectMapper.readTree(rewriteJson);

                rewriteEntity = new RewriteResultEntity();
                rewriteEntity.setUserId(HARDCODED_USER_ID);
                rewriteEntity.setResumeId(request.resumeId());
                rewriteEntity.setJdId(request.jdId());
                rewriteEntity.setMatchResultId(matchEntity.getId());
                rewriteEntity.setRewriteData(rewriteJson);
                rewriteEntity.setRewriteAttempts(intField(rewriteRoot, "rewrite_attempts"));
                rewriteEntity.setFidelityStatus(textField(rewriteRoot, "fidelity_status"));

                JsonNode fidelityReport = rewriteRoot.path("fidelity_report");
                if (!fidelityReport.isMissingNode() && !fidelityReport.isNull()) {
                    rewriteEntity.setFidelityScore(decimalField(fidelityReport, "fidelity_score"));
                }

                rewriteResultMapper.insert(rewriteEntity);

                log.info("Rewrite saved (id={}) attempts={} fidelity_status={}",
                        rewriteEntity.getId(), rewriteEntity.getRewriteAttempts(),
                        rewriteEntity.getFidelityStatus());

                // Persist the rewrite agent_run
                try {
                    agentRunService.saveFromResponse(rewriteJson, HARDCODED_USER_ID);
                } catch (Exception logEx) {
                    log.warn("Failed to persist rewrite agent_run (resumeId={} jdId={}): {}",
                            request.resumeId(), request.jdId(), logEx.getMessage());
                }
            }

            // ── Step 3: build combined response ──────────────────────────────
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.info("Full workflow complete — matchId={} elapsed={}ms", matchEntity.getId(), elapsedMs);

            Map<String, Object> response = new HashMap<>();
            response.put("match_result_id", matchEntity.getId());
            response.put("overall_score",   matchEntity.getOverallScore());
            response.put("skill_score",     matchEntity.getSkillScore());
            response.put("experience_score", matchEntity.getExperienceScore());
            response.put("keyword_score",   matchEntity.getKeywordScore());
            response.put("gap_analysis",    matchRoot);
            response.put("rewrite_triggered", rewriteRoot != null);

            if (rewriteRoot != null && rewriteEntity != null) {
                response.put("rewrite_result_id",  rewriteEntity.getId());
                response.put("rewrite_attempts",   rewriteEntity.getRewriteAttempts());
                response.put("fidelity_score",     rewriteEntity.getFidelityScore());
                response.put("fidelity_status",    rewriteEntity.getFidelityStatus());
                response.put("fidelity_report",    rewriteRoot.path("fidelity_report"));
                response.put("rewrite_result",     rewriteRoot);
            }

            return ResponseEntity.ok(response);

        } catch (Exception e) {
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.error("Full workflow failed after {}ms — resumeId={} jdId={}: {}",
                    elapsedMs, request.resumeId(), request.jdId(), e.getMessage());
            return ResponseEntity.internalServerError().body(
                    Map.of("error", "Full workflow failed: " + e.getMessage()));
        }
    }

    /**
     * Retrieve a previously saved full workflow result by its match_result ID.
     *
     * <p>Returns the persisted match scores and gap analysis. If a rewrite was
     * performed for the same resume+JD pair, the most recent rewrite result is
     * also included.
     */
    @GetMapping("/full/{matchResultId}")
    public ResponseEntity<Object> getFullWorkflowResult(@PathVariable Long matchResultId) {
        MatchResultEntity matchEntity = matchResultMapper.findById(matchResultId);
        if (matchEntity == null) {
            return ResponseEntity.notFound().build();
        }

        try {
            Map<String, Object> response = new HashMap<>();
            response.put("match_result_id",  matchEntity.getId());
            response.put("resume_id",        matchEntity.getResumeId());
            response.put("jd_id",            matchEntity.getJdId());
            response.put("overall_score",    matchEntity.getOverallScore());
            response.put("skill_score",      matchEntity.getSkillScore());
            response.put("experience_score", matchEntity.getExperienceScore());
            response.put("keyword_score",    matchEntity.getKeywordScore());
            response.put("created_at",       matchEntity.getCreatedAt());

            // Include parsed gap_analysis JSON inline rather than as a raw string
            if (matchEntity.getGapAnalysis() != null) {
                JsonNode gapNode = objectMapper.readTree(matchEntity.getGapAnalysis());
                response.put("gap_analysis", gapNode);
            }

            // Attach the most recent rewrite result for this resume+JD pair, if any
            java.util.List<RewriteResultEntity> rewrites = rewriteResultMapper.findByResumeIdAndJdId(
                    matchEntity.getResumeId(), matchEntity.getJdId());

            // findByResumeIdAndJdId returns rows ordered by created_at DESC — take the first
            RewriteResultEntity latestRewrite = rewrites.isEmpty() ? null : rewrites.get(0);

            response.put("rewrite_triggered", latestRewrite != null);

            if (latestRewrite != null) {
                response.put("rewrite_result_id", latestRewrite.getId());
                response.put("rewrite_attempts",  latestRewrite.getRewriteAttempts());
                response.put("fidelity_score",    latestRewrite.getFidelityScore());
                response.put("fidelity_status",   latestRewrite.getFidelityStatus());

                if (latestRewrite.getRewriteData() != null) {
                    JsonNode rewriteNode = objectMapper.readTree(latestRewrite.getRewriteData());
                    response.put("rewrite_result",  rewriteNode);
                    response.put("fidelity_report", rewriteNode.path("fidelity_report"));
                }
            }

            return ResponseEntity.ok(response);

        } catch (Exception e) {
            log.error("Failed to retrieve full workflow result for matchResultId={}: {}",
                    matchResultId, e.getMessage());
            return ResponseEntity.internalServerError().body(
                    Map.of("error", "Failed to retrieve workflow result: " + e.getMessage()));
        }
    }

    // -------------------------------------------------------------------------

    private BigDecimal decimalField(JsonNode node, String field) {
        if (node.hasNonNull(field)) {
            return new BigDecimal(node.get(field).asText());
        }
        return null;
    }

    private Integer intField(JsonNode node, String field) {
        if (node.hasNonNull(field)) {
            return node.get(field).asInt();
        }
        return null;
    }

    private String textField(JsonNode node, String field) {
        if (node.hasNonNull(field)) {
            return node.get(field).asText(null);
        }
        return null;
    }

    record WorkflowRunRequest(Long resumeId, Long jdId) {}

    record FullWorkflowRequest(Long resumeId, Long jdId) {}
}
