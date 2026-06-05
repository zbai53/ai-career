package com.aicareer.service;

import com.aicareer.config.AgentServiceConfig;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

@Service
public class AgentServiceClient {

    private final RestTemplate restTemplate;
    private final String agentServiceUrl;

    public AgentServiceClient(RestTemplate restTemplate, AgentServiceConfig agentServiceConfig) {
        this.restTemplate = restTemplate;
        this.agentServiceUrl = agentServiceConfig.getAgentServiceUrl();
    }

    public String checkHealth() {
        return restTemplate.getForObject(agentServiceUrl + "/health", String.class);
    }
}
