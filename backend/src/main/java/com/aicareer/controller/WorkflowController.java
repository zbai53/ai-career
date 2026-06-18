package com.aicareer.controller;

import com.aicareer.mapper.JobDescriptionMapper;
import com.aicareer.mapper.ResumeMapper;
import com.aicareer.model.entity.JobDescription;
import com.aicareer.model.entity.Resume;
import com.aicareer.service.AgentRunService;
import com.aicareer.service.AgentServiceClient;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/workflow")
public class WorkflowController {

    private static final Logger log = LoggerFactory.getLogger(WorkflowController.class);
    // Placeholder until real auth is wired in
    private static final long HARDCODED_USER_ID = 1L;

    private final ResumeMapper resumeMapper;
    private final JobDescriptionMapper jobDescriptionMapper;
    private final AgentServiceClient agentServiceClient;
    private final AgentRunService agentRunService;
    private final ObjectMapper objectMapper;

    public WorkflowController(ResumeMapper resumeMapper,
                              JobDescriptionMapper jobDescriptionMapper,
                              AgentServiceClient agentServiceClient,
                              AgentRunService agentRunService,
                              ObjectMapper objectMapper) {
        this.resumeMapper = resumeMapper;
        this.jobDescriptionMapper = jobDescriptionMapper;
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

    // -------------------------------------------------------------------------

    record WorkflowRunRequest(Long resumeId, Long jdId) {}
}
