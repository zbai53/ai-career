package com.aicareer.service;

import com.aicareer.mapper.InterviewSessionMapper;
import com.aicareer.mapper.JobDescriptionMapper;
import com.aicareer.mapper.ResumeMapper;
import com.aicareer.model.entity.InterviewSession;
import com.aicareer.model.entity.JobDescription;
import com.aicareer.model.entity.Resume;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.NoSuchElementException;

@Service
public class InterviewService {

    private static final Logger log = LoggerFactory.getLogger(InterviewService.class);

    private final ResumeMapper resumeMapper;
    private final JobDescriptionMapper jobDescriptionMapper;
    private final InterviewSessionMapper interviewSessionMapper;
    private final AgentServiceClient agentServiceClient;
    private final AgentRunService agentRunService;
    private final ObjectMapper objectMapper;

    public InterviewService(ResumeMapper resumeMapper,
                            JobDescriptionMapper jobDescriptionMapper,
                            InterviewSessionMapper interviewSessionMapper,
                            AgentServiceClient agentServiceClient,
                            AgentRunService agentRunService,
                            ObjectMapper objectMapper) {
        this.resumeMapper           = resumeMapper;
        this.jobDescriptionMapper   = jobDescriptionMapper;
        this.interviewSessionMapper = interviewSessionMapper;
        this.agentServiceClient     = agentServiceClient;
        this.agentRunService        = agentRunService;
        this.objectMapper           = objectMapper;
    }

    // -------------------------------------------------------------------------
    // Start a new interview session
    // -------------------------------------------------------------------------

    /**
     * Load resume and JD, call the agent service to create an interview session,
     * persist a new row in interview_sessions, and return the first question.
     *
     * @throws NoSuchElementException if resume or JD cannot be found
     * @throws RuntimeException       if the agent service call fails
     */
    public Map<String, Object> startSession(Long resumeId, Long jdId, int numQuestions, Long userId) {
        Resume resume = resumeMapper.findById(resumeId);
        if (resume == null) {
            throw new NoSuchElementException("Resume not found: " + resumeId);
        }

        JobDescription jd = jobDescriptionMapper.findById(jdId);
        if (jd == null) {
            throw new NoSuchElementException("JobDescription not found: " + jdId);
        }

        log.info("Calling agent service — startInterview resumeId={} jdId={} numQuestions={}",
                resumeId, jdId, numQuestions);

        String agentResponse;
        try {
            agentResponse = agentServiceClient.startInterview(
                    resume.getParsedData(), jd.getParsedData(), numQuestions);
        } catch (Exception e) {
            log.error("Agent service startInterview failed: {}", e.getMessage());
            throw new RuntimeException("Failed to start interview session: " + e.getMessage(), e);
        }

        JsonNode root = parseJson(agentResponse, "startInterview");

        // Persist session row
        InterviewSession session = new InterviewSession();
        session.setUserId(userId);
        session.setResumeId(resumeId);
        session.setJdId(jdId);
        session.setSessionId(root.path("session_id").asText());
        session.setStatus("active");
        session.setQuestionCount(0);
        session.setConversation("[]");
        session.setStartedAt(LocalDateTime.now());
        interviewSessionMapper.insert(session);

        log.info("Interview session created — db_id={} session_id={}", session.getId(), session.getSessionId());

        return Map.of(
                "db_id",           session.getId(),
                "session_id",      root.path("session_id").asText(),
                "question",        root.path("question").asText(""),
                "question_number", root.path("question_number").asInt(1),
                "total_questions", root.path("total_questions").asInt(numQuestions),
                "type",            root.path("type").asText(""),
                "difficulty",      root.path("difficulty").asText("")
        );
    }

    // -------------------------------------------------------------------------
    // Submit an answer for the active question
    // -------------------------------------------------------------------------

    /**
     * Forward the candidate's answer to the agent service, persist the updated
     * conversation in the DB, and return the full turn result.
     *
     * <p>The {@code dbId} is the primary key of the interview_sessions row —
     * the caller is expected to resolve it from the session_id before calling
     * this method.
     *
     * @throws RuntimeException if the agent service call fails
     */
    public Map<String, Object> submitAnswer(String sessionId, String answer, Long dbId) {
        log.info("Calling agent service — answerInterview sessionId={}", sessionId);

        String agentResponse;
        try {
            agentResponse = agentServiceClient.answerInterview(sessionId, answer);
        } catch (Exception e) {
            log.error("Agent service answerInterview failed (sessionId={}): {}", sessionId, e.getMessage());
            throw new RuntimeException("Failed to submit answer: " + e.getMessage(), e);
        }

        JsonNode root = parseJson(agentResponse, "answerInterview");

        // Only update the DB when the session is not yet done; the "done" response
        // carries no conversation_history and question_number is absent.
        boolean isComplete = root.path("is_complete").asBoolean(false);
        if (!isComplete) {
            String conversationJson = extractConversationJson(root);
            int questionCount = root.path("question_number").asInt(0);
            if (questionCount > 0 || !conversationJson.equals("[]")) {
                interviewSessionMapper.updateConversation(dbId, conversationJson, questionCount);
            }
        }

        return toMap(root);
    }

    // -------------------------------------------------------------------------
    // End the session and store the review
    // -------------------------------------------------------------------------

    /**
     * Call the agent service end endpoint, persist the final state (status,
     * conversation, review), log any embedded agent_run records, and return
     * the full session summary.
     *
     * @throws RuntimeException if the agent service call fails
     */
    public Map<String, Object> endSession(String sessionId, Long dbId, Long userId) {
        log.info("Calling agent service — endInterview sessionId={}", sessionId);

        String agentResponse;
        try {
            agentResponse = agentServiceClient.endInterview(sessionId);
        } catch (Exception e) {
            log.error("Agent service endInterview failed (sessionId={}): {}", sessionId, e.getMessage());
            throw new RuntimeException("Failed to end interview session: " + e.getMessage(), e);
        }

        JsonNode root = parseJson(agentResponse, "endInterview");

        String conversationJson = extractConversationJson(root);

        // Atomically persist status, review, and final conversation
        interviewSessionMapper.updateEnd(dbId, "completed", LocalDateTime.now(), agentResponse, conversationJson);

        // Non-fatal: log agent_run records embedded in the response
        try {
            agentRunService.saveFromResponse(agentResponse, userId);
        } catch (Exception e) {
            log.warn("Failed to persist agent_run for interview end (sessionId={}): {}", sessionId, e.getMessage());
        }

        log.info("Interview session ended — sessionId={} dbId={}", sessionId, dbId);

        return toMap(root);
    }

    // -------------------------------------------------------------------------
    // Private helpers
    // -------------------------------------------------------------------------

    private JsonNode parseJson(String json, String context) {
        try {
            return objectMapper.readTree(json);
        } catch (JsonProcessingException e) {
            log.error("Failed to parse agent-service response in {}: {}", context, e.getMessage());
            throw new RuntimeException("Invalid JSON response from agent service (" + context + ")", e);
        }
    }

    /**
     * Serialize the {@code conversation_history} array from a Python response,
     * falling back to {@code "[]"} if the field is absent or not an array.
     */
    private String extractConversationJson(JsonNode root) {
        JsonNode hist = root.path("conversation_history");
        if (hist.isArray()) {
            try {
                return objectMapper.writeValueAsString(hist);
            } catch (JsonProcessingException e) {
                log.warn("Failed to serialize conversation_history: {}", e.getMessage());
            }
        }
        return "[]";
    }

    private Map<String, Object> toMap(JsonNode node) {
        try {
            return objectMapper.convertValue(node, new TypeReference<>() {});
        } catch (Exception e) {
            log.warn("Failed to convert JsonNode to Map, returning empty map: {}", e.getMessage());
            return Map.of();
        }
    }
}
