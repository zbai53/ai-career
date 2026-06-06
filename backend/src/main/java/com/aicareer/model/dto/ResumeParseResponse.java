package com.aicareer.model.dto;

import java.time.LocalDateTime;
import java.util.Map;

public class ResumeParseResponse {

    private Long id;
    private Map<String, Object> parsedData;
    private String originalFileName;
    private LocalDateTime parsedAt;

    public ResumeParseResponse() {}

    public ResumeParseResponse(Long id, Map<String, Object> parsedData,
                                String originalFileName, LocalDateTime parsedAt) {
        this.id = id;
        this.parsedData = parsedData;
        this.originalFileName = originalFileName;
        this.parsedAt = parsedAt;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Map<String, Object> getParsedData() { return parsedData; }
    public void setParsedData(Map<String, Object> parsedData) { this.parsedData = parsedData; }

    public String getOriginalFileName() { return originalFileName; }
    public void setOriginalFileName(String originalFileName) { this.originalFileName = originalFileName; }

    public LocalDateTime getParsedAt() { return parsedAt; }
    public void setParsedAt(LocalDateTime parsedAt) { this.parsedAt = parsedAt; }
}
