package com.aicareer.service;

import com.aicareer.config.AgentServiceConfig;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

@Service
public class AgentServiceClient {

    private final RestTemplate restTemplate;
    private final RestTemplate agentRestTemplate;
    private final RestTemplate workflowRestTemplate;
    private final String agentServiceUrl;
    private final ObjectMapper objectMapper;

    public AgentServiceClient(
            RestTemplate restTemplate,
            @Qualifier("agentRestTemplate") RestTemplate agentRestTemplate,
            @Qualifier("workflowRestTemplate") RestTemplate workflowRestTemplate,
            AgentServiceConfig agentServiceConfig,
            ObjectMapper objectMapper) {
        this.restTemplate = restTemplate;
        this.agentRestTemplate = agentRestTemplate;
        this.workflowRestTemplate = workflowRestTemplate;
        this.agentServiceUrl = agentServiceConfig.getAgentServiceUrl();
        this.objectMapper = objectMapper;
    }

    public String checkHealth() {
        return restTemplate.getForObject(agentServiceUrl + "/health", String.class);
    }

    /**
     * Sends the file bytes to the agent-service resume parse endpoint as a
     * multipart/form-data POST and returns the raw JSON response body.
     *
     * @param fileBytes  raw bytes of the resume file
     * @param fileName   original file name (used to determine Content-Type)
     * @return JSON string representing the parsed resume
     * @throws RuntimeException on connection failure, timeout, or non-2xx response
     */
    public String parseResume(byte[] fileBytes, String fileName) {
        String url = agentServiceUrl + "/api/resume/parse";

        ByteArrayResource fileResource = new ByteArrayResource(fileBytes) {
            @Override
            public String getFilename() {
                return fileName;
            }
        };

        HttpHeaders fileHeaders = new HttpHeaders();
        fileHeaders.setContentType(resolveMediaType(fileName));

        HttpEntity<ByteArrayResource> filePart = new HttpEntity<>(fileResource, fileHeaders);

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", filePart);

        HttpHeaders requestHeaders = new HttpHeaders();
        requestHeaders.setContentType(MediaType.MULTIPART_FORM_DATA);

        HttpEntity<MultiValueMap<String, Object>> request = new HttpEntity<>(body, requestHeaders);

        try {
            ResponseEntity<String> response = agentRestTemplate.postForEntity(url, request, String.class);
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException(
                        "Resume parse failed with status " + response.getStatusCode()
                                + ": " + response.getBody());
            }
            return response.getBody();
        } catch (ResourceAccessException e) {
            throw new RuntimeException(
                    "Could not reach agent-service at " + url + " (connection/timeout): " + e.getMessage(), e);
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            throw new RuntimeException(
                    "Resume parse request failed (" + e.getStatusCode() + "): " + e.getResponseBodyAsString(), e);
        }
    }

    /**
     * Sends a JSON POST to the agent-service JD parse endpoint.
     * At least one of {@code text} or {@code url} should be non-null.
     *
     * @param text raw job description text (may be null if url is provided)
     * @param url  URL of a job posting page (may be null if text is provided)
     * @return JSON string representing the parsed job description
     * @throws RuntimeException on connection failure, timeout, or non-2xx response
     */
    public String parseJobDescription(String text, String url) {
        String endpoint = agentServiceUrl + "/api/jd/parse";

        Map<String, Object> body = new HashMap<>();
        if (text != null) body.put("text", text);
        if (url != null) body.put("url", url);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        HttpEntity<Map<String, Object>> request = new HttpEntity<>(body, headers);

        try {
            ResponseEntity<String> response = agentRestTemplate.postForEntity(endpoint, request, String.class);
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException(
                        "JD parse failed with status " + response.getStatusCode()
                                + ": " + response.getBody());
            }
            return response.getBody();
        } catch (ResourceAccessException e) {
            throw new RuntimeException(
                    "Could not reach agent-service at " + endpoint + " (connection/timeout): " + e.getMessage(), e);
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            throw new RuntimeException(
                    "JD parse request failed (" + e.getStatusCode() + "): " + e.getResponseBodyAsString(), e);
        }
    }

    /**
     * Sends a resume and job description to the agent-service match endpoint
     * and returns the raw JSON match result.
     *
     * @param resumeJson  parsedData JSON string from the resumes table
     * @param jdJson      parsedData JSON string from the job_descriptions table
     * @return JSON string representing the MatchResult
     */
    public String matchResumeToJD(String resumeJson, String jdJson) {
        String endpoint = agentServiceUrl + "/api/match";

        JsonNode resumeNode;
        JsonNode jdNode;
        try {
            resumeNode = objectMapper.readTree(resumeJson);
            jdNode = objectMapper.readTree(jdJson);
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to parse stored JSON before sending to agent-service: " + e.getMessage(), e);
        }

        Map<String, Object> body = new HashMap<>();
        body.put("resume", resumeNode);
        body.put("jd", jdNode);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        HttpEntity<Map<String, Object>> request = new HttpEntity<>(body, headers);

        try {
            ResponseEntity<String> response = agentRestTemplate.postForEntity(endpoint, request, String.class);
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException(
                        "Match failed with status " + response.getStatusCode() + ": " + response.getBody());
            }
            return response.getBody();
        } catch (ResourceAccessException e) {
            throw new RuntimeException(
                    "Could not reach agent-service at " + endpoint + " (connection/timeout): " + e.getMessage(), e);
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            throw new RuntimeException(
                    "Match request failed (" + e.getStatusCode() + "): " + e.getResponseBodyAsString(), e);
        }
    }

    /**
     * Invokes the full LangGraph workflow on the agent-service.
     *
     * <p>The workflow chains ResumeAgent → JDAgent → MatchAgent internally.
     * Inputs are file path and JD text that the Python service will process
     * directly, so the caller provides the raw values rather than parsed JSON.
     *
     * @param resumeFilePath absolute path to the resume file on the agent-service host
     * @param jdText         raw job description text (or a public URL)
     * @param userId         caller's user ID (used as the default thread_id)
     * @param threadId       optional checkpoint thread ID; null → defaults to userId
     * @return raw JSON string of the final workflow state (includes match_result, agent_runs, etc.)
     */
    public String runWorkflow(String resumeFilePath, String jdText, String userId, String threadId) {
        String endpoint = agentServiceUrl + "/api/workflow/run";

        Map<String, Object> body = new HashMap<>();
        body.put("user_id", userId);
        if (resumeFilePath != null) body.put("resume_file_path", resumeFilePath);
        if (jdText        != null) body.put("jd_text",           jdText);
        if (threadId      != null) body.put("thread_id",         threadId);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        HttpEntity<Map<String, Object>> request = new HttpEntity<>(body, headers);

        try {
            ResponseEntity<String> response = workflowRestTemplate.postForEntity(endpoint, request, String.class);
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException(
                        "Workflow run failed with status " + response.getStatusCode()
                                + ": " + response.getBody());
            }
            return response.getBody();
        } catch (ResourceAccessException e) {
            throw new RuntimeException(
                    "Could not reach agent-service workflow endpoint (connection/timeout): " + e.getMessage(), e);
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            throw new RuntimeException(
                    "Workflow run request failed (" + e.getStatusCode() + "): " + e.getResponseBodyAsString(), e);
        }
    }

    /**
     * Fetches the current checkpoint state for a given workflow thread.
     *
     * @param threadId the thread_id used when {@link #runWorkflow} was called
     * @return raw JSON string with current_step, next, is_complete, match_result, etc.
     */
    public String getWorkflowStatus(String threadId) {
        String endpoint = agentServiceUrl + "/api/workflow/status/" + threadId;

        try {
            ResponseEntity<String> response = restTemplate.getForEntity(endpoint, String.class);
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException(
                        "Workflow status failed with status " + response.getStatusCode()
                                + ": " + response.getBody());
            }
            return response.getBody();
        } catch (ResourceAccessException e) {
            throw new RuntimeException(
                    "Could not reach agent-service status endpoint (connection/timeout): " + e.getMessage(), e);
        } catch (HttpClientErrorException | HttpServerErrorException e) {
            throw new RuntimeException(
                    "Workflow status request failed (" + e.getStatusCode() + "): " + e.getResponseBodyAsString(), e);
        }
    }

    private MediaType resolveMediaType(String fileName) {
        if (fileName != null && fileName.toLowerCase().endsWith(".pdf")) {
            return MediaType.APPLICATION_PDF;
        }
        return MediaType.parseMediaType(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
    }
}
