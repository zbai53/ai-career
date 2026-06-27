package com.aicareer.mapper;

import com.aicareer.model.entity.InterviewSession;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.time.LocalDateTime;
import java.util.List;

@Mapper
public interface InterviewSessionMapper {

    void insert(InterviewSession session);

    InterviewSession findById(Long id);

    List<InterviewSession> findByUserId(Long userId);

    void updateStatus(@Param("id") Long id,
                      @Param("status") String status,
                      @Param("endedAt") LocalDateTime endedAt);

    InterviewSession findBySessionId(@Param("sessionId") String sessionId);

    List<InterviewSession> findByUserIdAndStatus(@Param("userId") Long userId,
                                                 @Param("status") String status);

    void updateConversation(@Param("id") Long id,
                            @Param("conversation") String conversation,
                            @Param("questionCount") int questionCount);

    void updateReview(@Param("id") Long id,
                      @Param("review") String review);

    void updateEnd(@Param("id") Long id,
                   @Param("status") String status,
                   @Param("endedAt") LocalDateTime endedAt,
                   @Param("review") String review,
                   @Param("conversation") String conversation);

    @Delete("DELETE FROM interview_sessions WHERE user_id = #{userId}")
    int deleteByUserId(Long userId);
}
