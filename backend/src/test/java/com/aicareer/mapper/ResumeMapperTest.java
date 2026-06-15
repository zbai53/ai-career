package com.aicareer.mapper;

import com.aicareer.model.entity.Resume;
import com.aicareer.model.entity.User;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
@Transactional
class ResumeMapperTest {

    @Autowired
    private UserMapper userMapper;

    @Autowired
    private ResumeMapper resumeMapper;

    private User testUser;

    @BeforeEach
    void setUp() {
        testUser = new User();
        testUser.setEmail("resume_test_" + System.nanoTime() + "@example.com");
        testUser.setPasswordHash("hashed_password");
        testUser.setName("Resume Test User");
        userMapper.insert(testUser);
    }

    private Resume buildResume(String fileName) {
        Resume resume = new Resume();
        resume.setUserId(testUser.getId());
        resume.setOriginalFileName(fileName);
        resume.setFilePath("/uploads/" + fileName);
        resume.setParsedData("{\"contact\":{\"name\":\"Test\"}}");
        resume.setRawText("Jane Doe\njane@example.com");
        resume.setParseConfidence(new BigDecimal("0.92"));
        return resume;
    }

    @Test
    void test_insertAndFindById() {
        Resume resume = buildResume("resume.pdf");
        resumeMapper.insert(resume);

        assertThat(resume.getId()).isNotNull();

        Resume found = resumeMapper.findById(resume.getId());

        assertThat(found).isNotNull();
        assertThat(found.getId()).isEqualTo(resume.getId());
        assertThat(found.getUserId()).isEqualTo(testUser.getId());
        assertThat(found.getOriginalFileName()).isEqualTo("resume.pdf");
        assertThat(found.getFilePath()).isEqualTo("/uploads/resume.pdf");
        assertThat(found.getParsedData()).contains("\"name\"").contains("Test");
        assertThat(found.getRawText()).isEqualTo("Jane Doe\njane@example.com");
        assertThat(found.getParseConfidence()).isEqualByComparingTo(new BigDecimal("0.92"));
        assertThat(found.getCreatedAt()).isNotNull();
    }

    @Test
    void test_findByUserId() {
        resumeMapper.insert(buildResume("first.pdf"));
        resumeMapper.insert(buildResume("second.pdf"));

        List<Resume> resumes = resumeMapper.findByUserId(testUser.getId());

        assertThat(resumes).hasSize(2);
        assertThat(resumes).extracting(Resume::getOriginalFileName)
                .containsExactlyInAnyOrder("first.pdf", "second.pdf");
    }

    @Test
    void test_findByUserId_empty() {
        // Insert a different user with no resumes
        User other = new User();
        other.setEmail("other_" + System.nanoTime() + "@example.com");
        other.setPasswordHash("hash");
        other.setName("Other");
        userMapper.insert(other);

        List<Resume> resumes = resumeMapper.findByUserId(other.getId());

        assertThat(resumes).isEmpty();
    }

    @Test
    void test_deleteById() {
        Resume resume = buildResume("to_delete.pdf");
        resumeMapper.insert(resume);
        assertThat(resumeMapper.findById(resume.getId())).isNotNull();

        resumeMapper.deleteById(resume.getId());

        assertThat(resumeMapper.findById(resume.getId())).isNull();
    }
}
