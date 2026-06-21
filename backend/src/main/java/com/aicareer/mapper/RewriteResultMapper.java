package com.aicareer.mapper;

import com.aicareer.model.entity.RewriteResultEntity;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface RewriteResultMapper {

    void insert(RewriteResultEntity rewriteResult);

    RewriteResultEntity findById(Long id);

    List<RewriteResultEntity> findByResumeIdAndJdId(
            @Param("resumeId") Long resumeId,
            @Param("jdId") Long jdId);
}
