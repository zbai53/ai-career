package com.aicareer.controller;

import com.aicareer.service.AgentServiceClient;
import com.aicareer.service.FileStorageService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;
import java.util.Set;

@RestController
@RequestMapping("/api/resumes")
public class ResumeController {

    private static final Logger log = LoggerFactory.getLogger(ResumeController.class);
    private static final Set<String> ALLOWED_EXTENSIONS = Set.of(".pdf", ".docx");

    private final AgentServiceClient agentServiceClient;
    private final FileStorageService fileStorageService;

    public ResumeController(AgentServiceClient agentServiceClient, FileStorageService fileStorageService) {
        this.agentServiceClient = agentServiceClient;
        this.fileStorageService = fileStorageService;
    }

    @PostMapping("/parse")
    public ResponseEntity<Object> parse(@RequestParam("file") MultipartFile file) {
        String originalName = file.getOriginalFilename() != null ? file.getOriginalFilename() : "";
        String extension = originalName.contains(".")
                ? originalName.substring(originalName.lastIndexOf('.')).toLowerCase()
                : "";

        if (!ALLOWED_EXTENSIONS.contains(extension)) {
            return ResponseEntity.badRequest().body(
                    Map.of("error", "Unsupported file type '" + extension + "'. Upload a .pdf or .docx file."));
        }

        long startMs = System.currentTimeMillis();
        log.info("Resume parse request — file: '{}', size: {} bytes", originalName, file.getSize());

        String savedPath = null;
        try {
            savedPath = fileStorageService.saveFile(file);
            String result = agentServiceClient.parseResume(file.getBytes(), originalName);
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.info("Resume '{}' parsed in {} ms", originalName, elapsedMs);
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.error("Resume parse failed for '{}' after {} ms: {}", originalName, elapsedMs, e.getMessage());
            return ResponseEntity.internalServerError().body(
                    Map.of("error", "Failed to parse resume: " + e.getMessage()));
        } finally {
            if (savedPath != null) {
                fileStorageService.deleteFile(savedPath);
            }
        }
    }
}
