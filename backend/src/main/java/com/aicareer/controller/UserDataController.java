package com.aicareer.controller;

import com.aicareer.service.DataDeletionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/users")
public class UserDataController {

    private static final Logger log = LoggerFactory.getLogger(UserDataController.class);

    // Placeholder until real JWT/session auth is wired in (same pattern as InterviewController)
    private static final long HARDCODED_USER_ID = 1L;

    private final DataDeletionService dataDeletionService;

    public UserDataController(DataDeletionService dataDeletionService) {
        this.dataDeletionService = dataDeletionService;
    }

    /**
     * DELETE /api/users/me/data
     *
     * Permanently removes all data associated with the authenticated user:
     * resumes, job descriptions, match results, rewrite results,
     * interview sessions, and agent run logs.
     *
     * Returns 200 with a confirmation payload on success.
     */
    @DeleteMapping("/me/data")
    public ResponseEntity<Object> deleteMyData() {
        log.info("DELETE /api/users/me/data — userId={}", HARDCODED_USER_ID);
        try {
            dataDeletionService.deleteAllUserData(HARDCODED_USER_ID);
            return ResponseEntity.ok(Map.of(
                "status",  "deleted",
                "message", "All your data has been removed"
            ));
        } catch (Exception e) {
            log.error("Data deletion failed for userId={}: {}", HARDCODED_USER_ID, e.getMessage());
            return ResponseEntity.internalServerError()
                    .body(Map.of("error", "Data deletion failed: " + e.getMessage()));
        }
    }
}
