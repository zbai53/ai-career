package com.aicareer.service;

import com.aicareer.mapper.ResumeMapper;
import com.aicareer.model.entity.Resume;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.math.BigDecimal;

@Service
public class ResumeService {

    private static final Logger log = LoggerFactory.getLogger(ResumeService.class);

    private final FileStorageService fileStorageService;
    private final AgentServiceClient agentServiceClient;
    private final ResumeMapper resumeMapper;
    private final ObjectMapper objectMapper;

    public ResumeService(FileStorageService fileStorageService,
                         AgentServiceClient agentServiceClient,
                         ResumeMapper resumeMapper,
                         ObjectMapper objectMapper) {
        this.fileStorageService = fileStorageService;
        this.agentServiceClient = agentServiceClient;
        this.resumeMapper = resumeMapper;
        this.objectMapper = objectMapper;
    }

    /**
     * Parses a resume file via the agent service and persists the result.
     *
     * @param file   uploaded resume file (.pdf or .docx)
     * @param userId owner of the resume
     * @return the persisted Resume entity with generated id
     */
    public Resume parseAndSave(MultipartFile file, Long userId) {
        String originalName = file.getOriginalFilename() != null ? file.getOriginalFilename() : "resume";
        String savedPath = null;

        try {
            savedPath = fileStorageService.saveFile(file);
            String parsedJson = agentServiceClient.parseResume(file.getBytes(), originalName);

            JsonNode root = objectMapper.readTree(parsedJson);

            BigDecimal parseConfidence = null;
            if (root.hasNonNull("parse_confidence")) {
                parseConfidence = new BigDecimal(root.get("parse_confidence").asText());
            }

            String rawText = root.hasNonNull("raw_text") ? root.get("raw_text").asText() : null;

            Resume resume = new Resume();
            resume.setUserId(userId);
            resume.setOriginalFileName(originalName);
            resume.setFilePath(savedPath);
            resume.setParsedData(parsedJson);
            resume.setRawText(rawText);
            resume.setParseConfidence(parseConfidence);

            resumeMapper.insert(resume);
            log.info("Resume '{}' persisted with id={} (userId={})", originalName, resume.getId(), userId);
            return resume;

        } catch (Exception e) {
            throw new RuntimeException("Failed to parse and save resume '" + originalName + "': " + e.getMessage(), e);
        } finally {
            if (savedPath != null) {
                fileStorageService.deleteFile(savedPath);
            }
        }
    }
}
