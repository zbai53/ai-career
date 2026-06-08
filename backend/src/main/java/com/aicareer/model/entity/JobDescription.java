package com.aicareer.model.entity;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public class JobDescription {

    private Long id;
    private Long userId;
    private String title;
    private String company;
    private String parsedData;
    private String rawText;
    private String sourceUrl;
    private BigDecimal parseConfidence;
    private LocalDateTime createdAt;

    public JobDescription() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }

    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }

    public String getCompany() { return company; }
    public void setCompany(String company) { this.company = company; }

    public String getParsedData() { return parsedData; }
    public void setParsedData(String parsedData) { this.parsedData = parsedData; }

    public String getRawText() { return rawText; }
    public void setRawText(String rawText) { this.rawText = rawText; }

    public String getSourceUrl() { return sourceUrl; }
    public void setSourceUrl(String sourceUrl) { this.sourceUrl = sourceUrl; }

    public BigDecimal getParseConfidence() { return parseConfidence; }
    public void setParseConfidence(BigDecimal parseConfidence) { this.parseConfidence = parseConfidence; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
