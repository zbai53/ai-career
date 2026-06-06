package com.aicareer.controller;

import com.aicareer.model.dto.JDParseRequest;
import com.aicareer.service.AgentServiceClient;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;

import java.util.Map;

@RestController
@RequestMapping("/api/jds")
public class JDController {

    private static final Logger log = LoggerFactory.getLogger(JDController.class);

    private final AgentServiceClient agentServiceClient;

    public JDController(AgentServiceClient agentServiceClient) {
        this.agentServiceClient = agentServiceClient;
    }

    @PostMapping("/parse")
    public ResponseEntity<Object> parse(@Valid @RequestBody JDParseRequest request) {
        boolean hasText = request.getText() != null && !request.getText().isBlank();
        String inputType = hasText ? "text" : "url";

        long startMs = System.currentTimeMillis();
        log.info("JD parse request — input type: {}", inputType);

        try {
            String result = agentServiceClient.parseJobDescription(request.getText(), request.getUrl());
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.info("JD parsed via {} in {} ms", inputType, elapsedMs);
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.error("JD parse failed via {} after {} ms: {}", inputType, elapsedMs, e.getMessage());
            return ResponseEntity.internalServerError().body(
                    Map.of("error", "Failed to parse job description: " + e.getMessage()));
        }
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Object> handleValidation(MethodArgumentNotValidException ex) {
        String message = ex.getBindingResult().getAllErrors().stream()
                .map(err -> err.getDefaultMessage())
                .findFirst()
                .orElse("Invalid request");
        return ResponseEntity.badRequest().body(Map.of("error", message));
    }
}
