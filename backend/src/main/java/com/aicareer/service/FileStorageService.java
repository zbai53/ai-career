package com.aicareer.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.UUID;

/**
 * Stores uploaded files in a local temp directory.
 * TODO: Replace with MinIO SDK implementation once object storage is wired up.
 */
@Service
public class FileStorageService {

    private static final Logger log = LoggerFactory.getLogger(FileStorageService.class);

    private final Path uploadDir;

    public FileStorageService(
            @Value("${file-storage.upload-dir:/tmp/ai-career-uploads}") String uploadDirPath) throws IOException {
        this.uploadDir = Paths.get(uploadDirPath);
        Files.createDirectories(this.uploadDir);
        log.info("FileStorageService initialised — upload dir: {}", this.uploadDir.toAbsolutePath());
    }

    /**
     * Saves the uploaded file to the configured upload directory with a UUID-prefixed name.
     *
     * @param file the uploaded multipart file
     * @return absolute path of the saved file
     * @throws RuntimeException if the file cannot be written
     */
    public String saveFile(MultipartFile file) {
        String originalName = file.getOriginalFilename() != null ? file.getOriginalFilename() : "upload";
        String extension = originalName.contains(".")
                ? originalName.substring(originalName.lastIndexOf('.'))
                : "";
        String savedName = UUID.randomUUID() + extension;
        Path destination = uploadDir.resolve(savedName);

        try {
            file.transferTo(destination);
            log.debug("Saved '{}' → {}", originalName, destination);
            return destination.toAbsolutePath().toString();
        } catch (IOException e) {
            throw new RuntimeException(
                    "Failed to save file '" + originalName + "' to " + destination + ": " + e.getMessage(), e);
        }
    }

    /**
     * Deletes a previously saved file. Logs a warning if the file does not exist.
     *
     * @param filePath absolute path returned by {@link #saveFile}
     */
    public void deleteFile(String filePath) {
        Path path = Paths.get(filePath);
        try {
            boolean deleted = Files.deleteIfExists(path);
            if (deleted) {
                log.debug("Deleted temp file: {}", path);
            } else {
                log.warn("Temp file not found for deletion: {}", path);
            }
        } catch (IOException e) {
            log.warn("Could not delete temp file '{}': {}", path, e.getMessage());
        }
    }
}
