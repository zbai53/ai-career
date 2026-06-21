package com.aicareer.model.entity;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public class RewriteResultEntity {

    private Long id;
    private Long userId;
    private Long resumeId;
    private Long jdId;
    private Long matchResultId;
    private String rewriteData;
    private BigDecimal fidelityScore;
    private Integer rewriteAttempts;
    private String fidelityStatus;
    private LocalDateTime createdAt;

    public RewriteResultEntity() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }

    public Long getResumeId() { return resumeId; }
    public void setResumeId(Long resumeId) { this.resumeId = resumeId; }

    public Long getJdId() { return jdId; }
    public void setJdId(Long jdId) { this.jdId = jdId; }

    public Long getMatchResultId() { return matchResultId; }
    public void setMatchResultId(Long matchResultId) { this.matchResultId = matchResultId; }

    public String getRewriteData() { return rewriteData; }
    public void setRewriteData(String rewriteData) { this.rewriteData = rewriteData; }

    public BigDecimal getFidelityScore() { return fidelityScore; }
    public void setFidelityScore(BigDecimal fidelityScore) { this.fidelityScore = fidelityScore; }

    public Integer getRewriteAttempts() { return rewriteAttempts; }
    public void setRewriteAttempts(Integer rewriteAttempts) { this.rewriteAttempts = rewriteAttempts; }

    public String getFidelityStatus() { return fidelityStatus; }
    public void setFidelityStatus(String fidelityStatus) { this.fidelityStatus = fidelityStatus; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
