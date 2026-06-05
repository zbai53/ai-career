package com.aicareer.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.client.RestTemplate;

@Configuration
public class AgentServiceConfig {

    @Value("${agent-service.url}")
    private String agentServiceUrl;

    public String getAgentServiceUrl() {
        return agentServiceUrl;
    }

    @Bean
    public RestTemplate restTemplate() {
        return new RestTemplate();
    }
}
