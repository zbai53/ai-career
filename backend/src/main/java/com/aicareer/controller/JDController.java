package com.aicareer.controller;

import com.aicareer.mapper.JobDescriptionMapper;
import com.aicareer.model.dto.JDParseRequest;
import com.aicareer.model.entity.JobDescription;
import com.aicareer.service.JobDescriptionService;
import jakarta.validation.Valid;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/jds")
public class JDController {

    private static final Logger log = LoggerFactory.getLogger(JDController.class);
    // Placeholder until real auth is wired in
    private static final long HARDCODED_USER_ID = 1L;

    private final JobDescriptionService jobDescriptionService;
    private final JobDescriptionMapper jobDescriptionMapper;

    public JDController(JobDescriptionService jobDescriptionService,
                        JobDescriptionMapper jobDescriptionMapper) {
        this.jobDescriptionService = jobDescriptionService;
        this.jobDescriptionMapper = jobDescriptionMapper;
    }

    @PostMapping("/parse")
    public ResponseEntity<Object> parse(@Valid @RequestBody JDParseRequest request) {
        boolean hasText = request.getText() != null && !request.getText().isBlank();
        String inputType = hasText ? "text" : "url";

        long startMs = System.currentTimeMillis();
        log.info("JD parse request — input type: {}", inputType);

        try {
            JobDescription jd = jobDescriptionService.parseAndSave(
                    request.getText(), request.getUrl(), HARDCODED_USER_ID);
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.info("JD parsed and saved (id={}) via {} in {} ms", jd.getId(), inputType, elapsedMs);
            return ResponseEntity.ok(jd);
        } catch (Exception e) {
            long elapsedMs = System.currentTimeMillis() - startMs;
            log.error("JD parse failed via {} after {} ms: {}", inputType, elapsedMs, e.getMessage());
            return ResponseEntity.internalServerError().body(
                    Map.of("error", "Failed to parse job description: " + e.getMessage()));
        }
    }

    @GetMapping("/{id}")
    public ResponseEntity<Object> findById(@PathVariable Long id) {
        JobDescription jd = jobDescriptionMapper.findById(id);
        if (jd == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(jd);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Object> handleValidation(MethodArgumentNotValidException ex) {
        String message = ex.getBindingResult().getAllErrors().stream()
                .map(err -> err.getDefaultMessage())
                .findFirst()
                .orElse("Invalid request");
        return ResponseEntity.badRequest().body(Map.of("error", message));
    }
}
