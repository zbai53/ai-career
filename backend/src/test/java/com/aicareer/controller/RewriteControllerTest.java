package com.aicareer.controller;

import com.aicareer.config.SecurityConfig;
import com.aicareer.mapper.JobDescriptionMapper;
import com.aicareer.mapper.MatchResultMapper;
import com.aicareer.mapper.ResumeMapper;
import com.aicareer.mapper.RewriteResultMapper;
import com.aicareer.model.entity.JobDescription;
import com.aicareer.model.entity.Resume;
import com.aicareer.service.AgentRunService;
import com.aicareer.service.AgentServiceClient;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(RewriteController.class)
@Import(SecurityConfig.class)
class RewriteControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ResumeMapper resumeMapper;

    @MockBean
    private JobDescriptionMapper jobDescriptionMapper;

    @MockBean
    private MatchResultMapper matchResultMapper;

    @MockBean
    private RewriteResultMapper rewriteResultMapper;

    @MockBean
    private AgentServiceClient agentServiceClient;

    @MockBean
    private AgentRunService agentRunService;

    @Test
    void post_returns404_whenResumeNotFound() throws Exception {
        when(resumeMapper.findById(99L)).thenReturn(null);

        mockMvc.perform(post("/api/rewrite")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"resumeId\":99,\"jdId\":1,\"matchResultId\":1}"))
                .andExpect(status().isNotFound());
    }

    @Test
    void post_returns404_whenJdNotFound() throws Exception {
        Resume resume = new Resume();
        resume.setId(1L);
        resume.setParsedData("{\"contact\":{\"name\":\"Test\"}}");
        when(resumeMapper.findById(1L)).thenReturn(resume);
        when(jobDescriptionMapper.findById(99L)).thenReturn(null);

        mockMvc.perform(post("/api/rewrite")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"resumeId\":1,\"jdId\":99,\"matchResultId\":1}"))
                .andExpect(status().isNotFound());
    }

    @Test
    void post_returns404_whenMatchResultNotFound() throws Exception {
        Resume resume = new Resume();
        resume.setId(1L);
        resume.setParsedData("{\"contact\":{\"name\":\"Test\"}}");
        when(resumeMapper.findById(1L)).thenReturn(resume);

        JobDescription jd = new JobDescription();
        jd.setId(1L);
        jd.setParsedData("{\"title\":\"Engineer\"}");
        when(jobDescriptionMapper.findById(1L)).thenReturn(jd);

        when(matchResultMapper.findById(99L)).thenReturn(null);

        mockMvc.perform(post("/api/rewrite")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"resumeId\":1,\"jdId\":1,\"matchResultId\":99}"))
                .andExpect(status().isNotFound());
    }
}
