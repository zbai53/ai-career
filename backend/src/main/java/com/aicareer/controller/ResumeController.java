package com.aicareer.controller;

import com.aicareer.mapper.ResumeMapper;
import com.aicareer.model.entity.Resume;
import com.aicareer.service.ResumeService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;
import java.util.Set;

@RestController
@RequestMapping("/api/resumes")
public class ResumeController {

    private static final Logger log = LoggerFactory.getLogger(ResumeController.class);
    private static final Set<String> ALLOWED_EXTENSIONS = Set.of(".pdf", ".docx");
    // Placeholder until real auth is wired in
    private static final long HARDCODED_USER_ID = 1L;

    private final ResumeService resumeService;
    private final ResumeMapper resumeMapper;

    public ResumeController(ResumeService resumeService, ResumeMapper resumeMapper) {
        this.resumeService = resumeService;
        this.resumeMapper = resumeMapper;
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

        try {
            Resume resume = resumeService.parseAndSave(file, HARDCODED_USER_ID);
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.info("Resume '{}' parsed and saved (id={}) in {} ms", originalName, resume.getId(), elapsedMs);
            return ResponseEntity.ok(resume);
        } catch (Exception e) {
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.error("Resume parse failed for '{}' after {} ms: {}", originalName, elapsedMs, e.getMessage());
            return ResponseEntity.internalServerError().body(
                    Map.of("error", "Failed to parse resume: " + e.getMessage()));
        }
    }

    @GetMapping("/{id}")
    public ResponseEntity<Object> findById(@PathVariable Long id) {
        Resume resume = resumeMapper.findById(id);
        if (resume == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(resume);
    }
}
