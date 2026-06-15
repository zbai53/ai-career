package com.aicareer.service;

import com.aicareer.mapper.JobDescriptionMapper;
import com.aicareer.model.entity.JobDescription;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;

@Service
public class JobDescriptionService {

    private static final Logger log = LoggerFactory.getLogger(JobDescriptionService.class);

    private final AgentServiceClient agentServiceClient;
    private final JobDescriptionMapper jobDescriptionMapper;
    private final ObjectMapper objectMapper;

    public JobDescriptionService(AgentServiceClient agentServiceClient,
                                 JobDescriptionMapper jobDescriptionMapper,
                                 ObjectMapper objectMapper) {
        this.agentServiceClient = agentServiceClient;
        this.jobDescriptionMapper = jobDescriptionMapper;
        this.objectMapper = objectMapper;
    }

    /**
     * Parses a job description via the agent service and persists the result.
     *
     * @param text   raw JD text (may be null if url is provided)
     * @param url    URL of a job posting page (may be null if text is provided)
     * @param userId owner of the job description
     * @return the persisted JobDescription entity with generated id
     */
    public JobDescription parseAndSave(String text, String url, Long userId) {
        try {
            String parsedJson = agentServiceClient.parseJobDescription(text, url);

            JsonNode root = objectMapper.readTree(parsedJson);

            String title = root.hasNonNull("title") ? root.get("title").asText(null) : null;
            String company = root.hasNonNull("company") ? root.get("company").asText(null) : null;
            String rawText = root.hasNonNull("raw_text") ? root.get("raw_text").asText(null) : null;
            String sourceUrl = root.hasNonNull("source_url") ? root.get("source_url").asText(null) : url;

            BigDecimal parseConfidence = null;
            if (root.hasNonNull("parse_confidence")) {
                parseConfidence = new BigDecimal(root.get("parse_confidence").asText());
            }

            JobDescription jd = new JobDescription();
            jd.setUserId(userId);
            jd.setTitle(title);
            jd.setCompany(company);
            jd.setParsedData(parsedJson);
            jd.setRawText(rawText);
            jd.setSourceUrl(sourceUrl);
            jd.setParseConfidence(parseConfidence);

            jobDescriptionMapper.insert(jd);
            log.info("JobDescription '{}' at '{}' persisted with id={} (userId={})",
                    title, sourceUrl, jd.getId(), userId);
            return jd;

        } catch (Exception e) {
            throw new RuntimeException("Failed to parse and save job description: " + e.getMessage(), e);
        }
    }
}
