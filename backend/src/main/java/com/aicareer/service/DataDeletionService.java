package com.aicareer.service;

import com.aicareer.mapper.AgentRunMapper;
import com.aicareer.mapper.InterviewSessionMapper;
import com.aicareer.mapper.JobDescriptionMapper;
import com.aicareer.mapper.MatchResultMapper;
import com.aicareer.mapper.ResumeMapper;
import com.aicareer.mapper.RewriteResultMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Deletes all data belonging to a user across every table.
 *
 * Deletion order respects foreign-key constraints:
 *   1. interview_sessions  (FK → resumes, job_descriptions)
 *   2. rewrite_results     (FK → match_results → resumes, job_descriptions)
 *   3. match_results       (FK → resumes, job_descriptions)
 *   4. agent_runs          (FK → user only)
 *   5. job_descriptions    (FK → user only)
 *   6. resumes             (FK → user only — must be last)
 */
@Service
public class DataDeletionService {

    private static final Logger log = LoggerFactory.getLogger(DataDeletionService.class);

    private final InterviewSessionMapper interviewSessionMapper;
    private final RewriteResultMapper    rewriteResultMapper;
    private final MatchResultMapper      matchResultMapper;
    private final AgentRunMapper         agentRunMapper;
    private final JobDescriptionMapper   jobDescriptionMapper;
    private final ResumeMapper           resumeMapper;

    public DataDeletionService(
            InterviewSessionMapper interviewSessionMapper,
            RewriteResultMapper    rewriteResultMapper,
            MatchResultMapper      matchResultMapper,
            AgentRunMapper         agentRunMapper,
            JobDescriptionMapper   jobDescriptionMapper,
            ResumeMapper           resumeMapper) {
        this.interviewSessionMapper = interviewSessionMapper;
        this.rewriteResultMapper    = rewriteResultMapper;
        this.matchResultMapper      = matchResultMapper;
        this.agentRunMapper         = agentRunMapper;
        this.jobDescriptionMapper   = jobDescriptionMapper;
        this.resumeMapper           = resumeMapper;
    }

    /**
     * Delete every row owned by {@code userId} across all tables,
     * in foreign-key-safe order, within a single transaction.
     *
     * @param userId the user whose data should be permanently removed
     */
    @Transactional
    public void deleteAllUserData(Long userId) {
        log.info("DataDeletionService: beginning full data deletion for userId={}", userId);

        int sessions  = interviewSessionMapper.deleteByUserId(userId);
        log.info("  deleted {} interview_session(s) for userId={}", sessions, userId);

        int rewrites  = rewriteResultMapper.deleteByUserId(userId);
        log.info("  deleted {} rewrite_result(s) for userId={}", rewrites, userId);

        int matches   = matchResultMapper.deleteByUserId(userId);
        log.info("  deleted {} match_result(s) for userId={}", matches, userId);

        int agentRuns = agentRunMapper.deleteByUserId(userId);
        log.info("  deleted {} agent_run(s) for userId={}", agentRuns, userId);

        int jds       = jobDescriptionMapper.deleteByUserId(userId);
        log.info("  deleted {} job_description(s) for userId={}", jds, userId);

        int resumes   = resumeMapper.deleteByUserId(userId);
        log.info("  deleted {} resume(s) for userId={}", resumes, userId);

        log.info(
            "DataDeletionService: deletion complete for userId={} — "
            + "sessions={} rewrites={} matches={} agentRuns={} jds={} resumes={}",
            userId, sessions, rewrites, matches, agentRuns, jds, resumes
        );
    }
}
