package com.aicareer.controller;

import com.aicareer.mapper.JobDescriptionMapper;
import com.aicareer.mapper.MatchResultMapper;
import com.aicareer.mapper.ResumeMapper;
import com.aicareer.model.entity.JobDescription;
import com.aicareer.model.entity.MatchResultEntity;
import com.aicareer.model.entity.Resume;
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
@RequestMapping("/api/match")
public class MatchController {

    private static final Logger log = LoggerFactory.getLogger(MatchController.class);
    // Placeholder until real auth is wired in
    private static final long HARDCODED_USER_ID = 1L;

    private final ResumeMapper resumeMapper;
    private final JobDescriptionMapper jobDescriptionMapper;
    private final MatchResultMapper matchResultMapper;
    private final AgentServiceClient agentServiceClient;
    private final AgentRunService agentRunService;
    private final ObjectMapper objectMapper;

    public MatchController(ResumeMapper resumeMapper,
                           JobDescriptionMapper jobDescriptionMapper,
                           MatchResultMapper matchResultMapper,
                           AgentServiceClient agentServiceClient,
                           AgentRunService agentRunService,
                           ObjectMapper objectMapper) {
        this.resumeMapper = resumeMapper;
        this.jobDescriptionMapper = jobDescriptionMapper;
        this.matchResultMapper = matchResultMapper;
        this.agentServiceClient = agentServiceClient;
        this.agentRunService = agentRunService;
        this.objectMapper = objectMapper;
    }

    @PostMapping
    public ResponseEntity<Object> match(@RequestBody MatchRequest request) {
        Resume resume = resumeMapper.findById(request.resumeId());
        if (resume == null) {
            return ResponseEntity.notFound().build();
        }

        JobDescription jd = jobDescriptionMapper.findById(request.jdId());
        if (jd == null) {
            return ResponseEntity.notFound().build();
        }

        long startMs = System.currentTimeMillis();
        log.info("Match request — resumeId={} jdId={}", request.resumeId(), request.jdId());

        try {
            String matchJson = agentServiceClient.matchResumeToJD(
                    resume.getParsedData(), jd.getParsedData());

            JsonNode root = objectMapper.readTree(matchJson);

            MatchResultEntity entity = new MatchResultEntity();
            entity.setUserId(HARDCODED_USER_ID);
            entity.setResumeId(request.resumeId());
            entity.setJdId(request.jdId());
            entity.setOverallScore(decimalField(root, "overall_score"));
            entity.setSkillScore(decimalField(root, "skill_score"));
            entity.setExperienceScore(decimalField(root, "experience_score"));
            entity.setKeywordScore(decimalField(root, "keyword_score"));
            entity.setGapAnalysis(matchJson);

            matchResultMapper.insert(entity);

            long elapsedMs = System.currentTimeMillis() - startMs;
            log.info("Match saved (id={}) in {} ms — overall={}", entity.getId(), elapsedMs, entity.getOverallScore());

            try {
                agentRunService.saveFromResponse(matchJson, HARDCODED_USER_ID);
            } catch (Exception logEx) {
                log.warn("Failed to persist agent_run log for match (resumeId={} jdId={}): {}",
                        request.resumeId(), request.jdId(), logEx.getMessage());
            }

            return ResponseEntity.ok(root);

        } catch (Exception e) {
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.error("Match failed after {} ms: {}", elapsedMs, e.getMessage());
            return ResponseEntity.internalServerError().body(
                    Map.of("error", "Match failed: " + e.getMessage()));
        }
    }

    @GetMapping("/{id}")
    public ResponseEntity<Object> findById(@PathVariable Long id) {
        MatchResultEntity entity = matchResultMapper.findById(id);
        if (entity == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(entity);
    }

    // -------------------------------------------------------------------------

    private BigDecimal decimalField(JsonNode root, String field) {
        if (root.hasNonNull(field)) {
            return new BigDecimal(root.get(field).asText());
        }
        return null;
    }

    record MatchRequest(Long resumeId, Long jdId) {}
}
