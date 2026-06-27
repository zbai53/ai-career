package com.aicareer.mapper;

import com.aicareer.model.entity.JobDescription;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;

import java.util.List;

@Mapper
public interface JobDescriptionMapper {

    void insert(JobDescription jobDescription);

    JobDescription findById(Long id);

    List<JobDescription> findByUserId(Long userId);

    void deleteById(Long id);

    @Delete("DELETE FROM job_descriptions WHERE user_id = #{userId}")
    int deleteByUserId(Long userId);
}
