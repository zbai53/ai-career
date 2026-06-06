package com.aicareer.model.dto;

import jakarta.validation.constraints.AssertTrue;

public class JDParseRequest {

    private String text;
    private String url;

    public JDParseRequest() {}

    public JDParseRequest(String text, String url) {
        this.text = text;
        this.url = url;
    }

    public String getText() { return text; }
    public void setText(String text) { this.text = text; }

    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }

    @AssertTrue(message = "At least one of 'text' or 'url' must be provided")
    public boolean isAtLeastOneProvided() {
        return (text != null && !text.isBlank()) || (url != null && !url.isBlank());
    }
}
