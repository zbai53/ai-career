package com.aicareer.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestTemplate;

@Configuration
public class AgentServiceConfig {

    @Value("${agent-service.url}")
    private String agentServiceUrl;

    public String getAgentServiceUrl() {
        return agentServiceUrl;
    }

    /** Default RestTemplate for general use (short timeout). */
    @Bean
    @Primary
    public RestTemplate restTemplate() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10_000);
        factory.setReadTimeout(30_000);
        return new RestTemplate(factory);
    }

    /** RestTemplate with a 60-second read timeout for calls that invoke Claude. */
    @Bean("agentRestTemplate")
    public RestTemplate agentRestTemplate() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10_000);
        factory.setReadTimeout(60_000);
        return new RestTemplate(factory);
    }

    /**
     * RestTemplate with a 120-second read timeout for workflow calls that chain
     * multiple agent invocations (resume parse → JD parse → match).
     */
    @Bean("workflowRestTemplate")
    public RestTemplate workflowRestTemplate() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(10_000);
        factory.setReadTimeout(120_000);
        return new RestTemplate(factory);
    }
}
