package com.aicareer.mapper;

import com.aicareer.model.entity.JobDescription;
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
class JobDescriptionMapperTest {

    @Autowired
    private UserMapper userMapper;

    @Autowired
    private JobDescriptionMapper jobDescriptionMapper;

    private User testUser;

    @BeforeEach
    void setUp() {
        testUser = new User();
        testUser.setEmail("jd_test_" + System.nanoTime() + "@example.com");
        testUser.setPasswordHash("hashed_password");
        testUser.setName("JD Test User");
        userMapper.insert(testUser);
    }

    private JobDescription buildJD(String title) {
        JobDescription jd = new JobDescription();
        jd.setUserId(testUser.getId());
        jd.setTitle(title);
        jd.setCompany("Acme Corp");
        jd.setParsedData("{\"title\":\"" + title + "\",\"company\":\"Acme Corp\"}");
        jd.setRawText("We are looking for a " + title);
        jd.setSourceUrl("https://example.com/jobs/1");
        jd.setParseConfidence(new BigDecimal("0.88"));
        return jd;
    }

    @Test
    void test_insertAndFindById() {
        JobDescription jd = buildJD("Senior Backend Engineer");
        jobDescriptionMapper.insert(jd);

        assertThat(jd.getId()).isNotNull();

        JobDescription found = jobDescriptionMapper.findById(jd.getId());

        assertThat(found).isNotNull();
        assertThat(found.getId()).isEqualTo(jd.getId());
        assertThat(found.getUserId()).isEqualTo(testUser.getId());
        assertThat(found.getTitle()).isEqualTo("Senior Backend Engineer");
        assertThat(found.getCompany()).isEqualTo("Acme Corp");
        assertThat(found.getParsedData()).contains("\"company\"").contains("Acme Corp");
        assertThat(found.getRawText()).startsWith("We are looking for a");
        assertThat(found.getSourceUrl()).isEqualTo("https://example.com/jobs/1");
        assertThat(found.getParseConfidence()).isEqualByComparingTo(new BigDecimal("0.88"));
        assertThat(found.getCreatedAt()).isNotNull();
    }

    @Test
    void test_findByUserId() {
        jobDescriptionMapper.insert(buildJD("Backend Engineer"));
        jobDescriptionMapper.insert(buildJD("Frontend Engineer"));

        List<JobDescription> jds = jobDescriptionMapper.findByUserId(testUser.getId());

        assertThat(jds).hasSize(2);
        assertThat(jds).extracting(JobDescription::getTitle)
                .containsExactlyInAnyOrder("Backend Engineer", "Frontend Engineer");
    }

    @Test
    void test_deleteById() {
        JobDescription jd = buildJD("To Be Deleted");
        jobDescriptionMapper.insert(jd);
        assertThat(jobDescriptionMapper.findById(jd.getId())).isNotNull();

        jobDescriptionMapper.deleteById(jd.getId());

        assertThat(jobDescriptionMapper.findById(jd.getId())).isNull();
    }
}
