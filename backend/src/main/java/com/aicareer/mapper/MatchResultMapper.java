package com.aicareer.mapper;

import com.aicareer.model.entity.MatchResultEntity;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface MatchResultMapper {

    void insert(MatchResultEntity matchResult);

    MatchResultEntity findById(Long id);

    List<MatchResultEntity> findByResumeIdAndJdId(
            @Param("resumeId") Long resumeId,
            @Param("jdId") Long jdId);
}
