package com.aicareer.model.entity;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public class Resume {

    private Long id;
    private Long userId;
    private String originalFileName;
    private String filePath;
    private String parsedData;
    private String rawText;
    private BigDecimal parseConfidence;
    private LocalDateTime createdAt;

    public Resume() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }

    public String getOriginalFileName() { return originalFileName; }
    public void setOriginalFileName(String originalFileName) { this.originalFileName = originalFileName; }

    public String getFilePath() { return filePath; }
    public void setFilePath(String filePath) { this.filePath = filePath; }

    public String getParsedData() { return parsedData; }
    public void setParsedData(String parsedData) { this.parsedData = parsedData; }

    public String getRawText() { return rawText; }
    public void setRawText(String rawText) { this.rawText = rawText; }

    public BigDecimal getParseConfidence() { return parseConfidence; }
    public void setParseConfidence(BigDecimal parseConfidence) { this.parseConfidence = parseConfidence; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
