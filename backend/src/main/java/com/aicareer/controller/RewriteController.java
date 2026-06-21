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
import java.util.Map;

@RestController
@RequestMapping("/api/rewrite")
public class RewriteController {

    private static final Logger log = LoggerFactory.getLogger(RewriteController.class);
    // Placeholder until real auth is wired in
    private static final long HARDCODED_USER_ID = 1L;

    private final ResumeMapper resumeMapper;
    private final JobDescriptionMapper jobDescriptionMapper;
    private final MatchResultMapper matchResultMapper;
    private final RewriteResultMapper rewriteResultMapper;
    private final AgentServiceClient agentServiceClient;
    private final AgentRunService agentRunService;
    private final ObjectMapper objectMapper;

    public RewriteController(ResumeMapper resumeMapper,
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

    @PostMapping
    public ResponseEntity<Object> rewrite(@RequestBody RewriteRequest request) {
        Resume resume = resumeMapper.findById(request.resumeId());
        if (resume == null) {
            return ResponseEntity.notFound().build();
        }

        JobDescription jd = jobDescriptionMapper.findById(request.jdId());
        if (jd == null) {
            return ResponseEntity.notFound().build();
        }

        MatchResultEntity matchResult = matchResultMapper.findById(request.matchResultId());
        if (matchResult == null) {
            return ResponseEntity.notFound().build();
        }

        long startMs = System.currentTimeMillis();
        log.info("Rewrite request — resumeId={} jdId={} matchResultId={}",
                request.resumeId(), request.jdId(), request.matchResultId());

        try {
            String rewriteJson = agentServiceClient.rewriteResume(
                    resume.getParsedData(),
                    jd.getParsedData(),
                    matchResult.getGapAnalysis());

            JsonNode root = objectMapper.readTree(rewriteJson);

            RewriteResultEntity entity = new RewriteResultEntity();
            entity.setUserId(HARDCODED_USER_ID);
            entity.setResumeId(request.resumeId());
            entity.setJdId(request.jdId());
            entity.setMatchResultId(request.matchResultId());
            entity.setRewriteData(rewriteJson);
            entity.setRewriteAttempts(intField(root, "rewrite_attempts"));
            entity.setFidelityStatus(textField(root, "fidelity_status"));

            JsonNode fidelityReport = root.path("fidelity_report");
            if (!fidelityReport.isMissingNode() && !fidelityReport.isNull()) {
                entity.setFidelityScore(decimalField(fidelityReport, "fidelity_score"));
            }

            rewriteResultMapper.insert(entity);

            long elapsedMs = System.currentTimeMillis() - startMs;
            log.info("Rewrite saved (id={}) in {} ms — attempts={} fidelity_status={}",
                    entity.getId(), elapsedMs,
                    entity.getRewriteAttempts(), entity.getFidelityStatus());

            try {
                agentRunService.saveFromResponse(rewriteJson, HARDCODED_USER_ID);
            } catch (Exception logEx) {
                log.warn("Failed to persist agent_run log for rewrite (resumeId={} jdId={}): {}",
                        request.resumeId(), request.jdId(), logEx.getMessage());
            }

            return ResponseEntity.ok(root);

        } catch (Exception e) {
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.error("Rewrite failed after {} ms: {}", elapsedMs, e.getMessage());
            return ResponseEntity.internalServerError().body(
                    Map.of("error", "Rewrite failed: " + e.getMessage()));
        }
    }

    @GetMapping("/{id}")
    public ResponseEntity<Object> findById(@PathVariable Long id) {
        RewriteResultEntity entity = rewriteResultMapper.findById(id);
        if (entity == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(entity);
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

    record RewriteRequest(Long resumeId, Long jdId, Long matchResultId) {}
}
