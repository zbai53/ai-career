package com.aicareer.mapper;

import com.aicareer.model.entity.Resume;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;

import java.util.List;

@Mapper
public interface ResumeMapper {

    void insert(Resume resume);

    Resume findById(Long id);

    List<Resume> findByUserId(Long userId);

    void deleteById(Long id);

    @Delete("DELETE FROM resumes WHERE user_id = #{userId}")
    int deleteByUserId(Long userId);
}
