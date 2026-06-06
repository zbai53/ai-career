package com.aicareer.model.dto;

import java.time.LocalDateTime;
import java.util.Map;

public class JDParseResponse {

    private Long id;
    private Map<String, Object> parsedData;
    private String rawText;
    private LocalDateTime parsedAt;

    public JDParseResponse() {}

    public JDParseResponse(Long id, Map<String, Object> parsedData,
                            String rawText, LocalDateTime parsedAt) {
        this.id = id;
        this.parsedData = parsedData;
        this.rawText = rawText;
        this.parsedAt = parsedAt;
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Map<String, Object> getParsedData() { return parsedData; }
    public void setParsedData(Map<String, Object> parsedData) { this.parsedData = parsedData; }

    public String getRawText() { return rawText; }
    public void setRawText(String rawText) { this.rawText = rawText; }

    public LocalDateTime getParsedAt() { return parsedAt; }
    public void setParsedAt(LocalDateTime parsedAt) { this.parsedAt = parsedAt; }
}
