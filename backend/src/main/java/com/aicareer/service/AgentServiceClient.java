package com.aicareer.service;

import com.aicareer.config.AgentServiceConfig;
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
    private final String agentServiceUrl;

    public AgentServiceClient(
            RestTemplate restTemplate,
            @Qualifier("agentRestTemplate") RestTemplate agentRestTemplate,
            AgentServiceConfig agentServiceConfig) {
        this.restTemplate = restTemplate;
        this.agentRestTemplate = agentRestTemplate;
        this.agentServiceUrl = agentServiceConfig.getAgentServiceUrl();
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

    private MediaType resolveMediaType(String fileName) {
        if (fileName != null && fileName.toLowerCase().endsWith(".pdf")) {
            return MediaType.APPLICATION_PDF;
        }
        return MediaType.parseMediaType(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
    }
}
