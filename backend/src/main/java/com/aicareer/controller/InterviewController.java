package com.aicareer.controller;

import com.aicareer.mapper.InterviewSessionMapper;
import com.aicareer.model.entity.InterviewSession;
import com.aicareer.service.AgentServiceClient;
import com.aicareer.service.InterviewService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.NoSuchElementException;

@RestController
@RequestMapping("/api/interviews")
public class InterviewController {

    private static final Logger log = LoggerFactory.getLogger(InterviewController.class);
    private static final long HARDCODED_USER_ID = 1L;

    private final InterviewService interviewService;
    private final InterviewSessionMapper interviewSessionMapper;
    private final AgentServiceClient agentServiceClient;
    private final ObjectMapper objectMapper;

    public InterviewController(InterviewService interviewService,
                               InterviewSessionMapper interviewSessionMapper,
                               AgentServiceClient agentServiceClient,
                               ObjectMapper objectMapper) {
        this.interviewService       = interviewService;
        this.interviewSessionMapper = interviewSessionMapper;
        this.agentServiceClient     = agentServiceClient;
        this.objectMapper           = objectMapper;
    }

    // -------------------------------------------------------------------------
    // POST /api/interviews/start
    // -------------------------------------------------------------------------

    @PostMapping("/start")
    public ResponseEntity<Object> start(@RequestBody StartRequest request) {
        int numQuestions = (request.numQuestions() != null) ? request.numQuestions() : 5;
        log.info("POST /api/interviews/start — resumeId={} jdId={} numQuestions={}",
                request.resumeId(), request.jdId(), numQuestions);
        try {
            Map<String, Object> result = interviewService.startSession(
                    request.resumeId(), request.jdId(), numQuestions, HARDCODED_USER_ID);
            return ResponseEntity.ok(result);
        } catch (NoSuchElementException e) {
            return ResponseEntity.notFound().build();
        } catch (Exception e) {
            log.error("Interview start failed: {}", e.getMessage());
            return ResponseEntity.internalServerError().body(Map.of("error", e.getMessage()));
        }
    }

    // -------------------------------------------------------------------------
    // POST /api/interviews/{sessionId}/answer
    // -------------------------------------------------------------------------

    @PostMapping("/{sessionId}/answer")
    public ResponseEntity<Object> answer(@PathVariable String sessionId,
                                         @RequestBody AnswerRequest request) {
        InterviewSession session = interviewSessionMapper.findBySessionId(sessionId);
        if (session == null) {
            return ResponseEntity.notFound().build();
        }
        if ("completed".equals(session.getStatus())) {
            return ResponseEntity.status(409).body(Map.of("error", "Session is already completed"));
        }
        log.info("POST /api/interviews/{}/answer — dbId={}", sessionId, session.getId());
        try {
            Map<String, Object> result = interviewService.submitAnswer(
                    sessionId, request.answer(), session.getId());
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            log.error("Interview answer failed (sessionId={}): {}", sessionId, e.getMessage());
            return ResponseEntity.internalServerError().body(Map.of("error", e.getMessage()));
        }
    }

    // -------------------------------------------------------------------------
    // GET /api/interviews/{sessionId}
    // -------------------------------------------------------------------------

    @GetMapping("/{sessionId}")
    public ResponseEntity<Object> status(@PathVariable String sessionId) {
        InterviewSession session = interviewSessionMapper.findBySessionId(sessionId);
        if (session == null) {
            return ResponseEntity.notFound().build();
        }
        log.info("GET /api/interviews/{} — dbId={}", sessionId, session.getId());
        try {
            String agentResponse = agentServiceClient.getInterviewStatus(sessionId);
            JsonNode agentState  = objectMapper.readTree(agentResponse);
            return ResponseEntity.ok(Map.of(
                    "db_id",          session.getId(),
                    "session_id",     sessionId,
                    "status",         session.getStatus(),
                    "question_count", session.getQuestionCount(),
                    "started_at",     session.getStartedAt(),
                    "ended_at",       session.getEndedAt(),
                    "agent_state",    agentState
            ));
        } catch (Exception e) {
            log.error("Interview status failed (sessionId={}): {}", sessionId, e.getMessage());
            return ResponseEntity.internalServerError().body(Map.of("error", e.getMessage()));
        }
    }

    // -------------------------------------------------------------------------
    // POST /api/interviews/{sessionId}/end
    // -------------------------------------------------------------------------

    @PostMapping("/{sessionId}/end")
    public ResponseEntity<Object> end(@PathVariable String sessionId) {
        InterviewSession session = interviewSessionMapper.findBySessionId(sessionId);
        if (session == null) {
            return ResponseEntity.notFound().build();
        }
        log.info("POST /api/interviews/{}/end — dbId={}", sessionId, session.getId());
        try {
            Map<String, Object> result = interviewService.endSession(
                    sessionId, session.getId(), HARDCODED_USER_ID);
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            log.error("Interview end failed (sessionId={}): {}", sessionId, e.getMessage());
            return ResponseEntity.internalServerError().body(Map.of("error", e.getMessage()));
        }
    }

    // -------------------------------------------------------------------------
    // Request records
    // -------------------------------------------------------------------------

    record StartRequest(Long resumeId, Long jdId, Integer numQuestions) {}

    record AnswerRequest(String answer) {}
}
