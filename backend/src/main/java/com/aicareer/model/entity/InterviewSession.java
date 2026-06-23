package com.aicareer.model.entity;

import java.time.LocalDateTime;

public class InterviewSession {

    private Long id;
    private Long userId;
    private Long jdId;
    private Long resumeId;
    private String sessionId;     // Python-generated UUID
    private String status;
    private Integer questionCount;
    private String conversation;  // JSON stored as text
    private String review;        // JSON stored as text
    private LocalDateTime startedAt;
    private LocalDateTime endedAt;

    public InterviewSession() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getUserId() { return userId; }
    public void setUserId(Long userId) { this.userId = userId; }

    public Long getJdId() { return jdId; }
    public void setJdId(Long jdId) { this.jdId = jdId; }

    public Long getResumeId() { return resumeId; }
    public void setResumeId(Long resumeId) { this.resumeId = resumeId; }

    public String getSessionId() { return sessionId; }
    public void setSessionId(String sessionId) { this.sessionId = sessionId; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public Integer getQuestionCount() { return questionCount; }
    public void setQuestionCount(Integer questionCount) { this.questionCount = questionCount; }

    public String getConversation() { return conversation; }
    public void setConversation(String conversation) { this.conversation = conversation; }

    public String getReview() { return review; }
    public void setReview(String review) { this.review = review; }

    public LocalDateTime getStartedAt() { return startedAt; }
    public void setStartedAt(LocalDateTime startedAt) { this.startedAt = startedAt; }

    public LocalDateTime getEndedAt() { return endedAt; }
    public void setEndedAt(LocalDateTime endedAt) { this.endedAt = endedAt; }
}
