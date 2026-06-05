package com.aicareer.controller;

import com.aicareer.service.AgentServiceClient;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class HealthController {

    private final AgentServiceClient agentServiceClient;

    public HealthController(AgentServiceClient agentServiceClient) {
        this.agentServiceClient = agentServiceClient;
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "ok");
    }

    @GetMapping("/health/agent")
    public ResponseEntity<Object> agentHealth() {
        try {
            String result = agentServiceClient.checkHealth();
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                    .body(Map.of("status", "agent-service-unavailable"));
        }
    }
}
