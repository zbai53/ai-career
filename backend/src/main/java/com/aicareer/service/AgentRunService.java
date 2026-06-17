package com.aicareer.service;

import com.aicareer.mapper.AgentRunMapper;
import com.aicareer.model.entity.AgentRun;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class AgentRunService {

    private static final Logger log = LoggerFactory.getLogger(AgentRunService.class);

    private final AgentRunMapper agentRunMapper;
    private final ObjectMapper objectMapper;

    public AgentRunService(AgentRunMapper agentRunMapper, ObjectMapper objectMapper) {
        this.agentRunMapper = agentRunMapper;
        this.objectMapper = objectMapper;
    }

    /**
     * Extracts the {@code agent_run} object from a Python agent-service response JSON and
     * persists it as an {@link AgentRun} record.
     *
     * <p>Callers should wrap this in a try-catch so that a logging failure never breaks
     * the main request flow.
     *
     * @param responseJson full JSON string returned by the agent-service endpoint
     * @param userId       id of the user who triggered the agent run (may be null)
     */
    public void saveFromResponse(String responseJson, Long userId) {
        JsonNode root;
        try {
            root = objectMapper.readTree(responseJson);
        } catch (Exception e) {
            log.warn("AgentRunService: could not parse response JSON — skipping log: {}", e.getMessage());
            return;
        }

        JsonNode runNode = root.get("agent_run");
        if (runNode == null || runNode.isNull()) {
            log.debug("AgentRunService: no 'agent_run' field in response — skipping");
            return;
        }

        AgentRun agentRun = new AgentRun();
        agentRun.setUserId(userId);
        agentRun.setAgentName(textOrNull(runNode, "agent_name"));
        agentRun.setInputSummary(textOrNull(runNode, "input_summary"));
        agentRun.setOutputSummary(textOrNull(runNode, "output_summary"));
        agentRun.setStatus(textOrNull(runNode, "status"));
        agentRun.setModelName(textOrNull(runNode, "model_name"));
        agentRun.setErrorMessage(textOrNull(runNode, "error_message"));

        if (runNode.hasNonNull("duration_ms")) {
            agentRun.setDurationMs(runNode.get("duration_ms").asInt());
        }
        if (runNode.hasNonNull("token_count")) {
            agentRun.setTokenCount(runNode.get("token_count").asInt());
        }

        agentRunMapper.insert(agentRun);
        log.debug("AgentRun persisted: id={} agent={} status={} duration={}ms tokens={}",
                agentRun.getId(), agentRun.getAgentName(), agentRun.getStatus(),
                agentRun.getDurationMs(), agentRun.getTokenCount());
    }

    private String textOrNull(JsonNode node, String field) {
        return node.hasNonNull(field) ? node.get(field).asText(null) : null;
    }
}
