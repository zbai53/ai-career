package com.aicareer.mapper;

import com.aicareer.model.entity.InterviewSession;
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
}
