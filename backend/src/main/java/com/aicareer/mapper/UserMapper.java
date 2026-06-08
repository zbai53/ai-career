package com.aicareer.mapper;

import com.aicareer.model.entity.User;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface UserMapper {

    void insert(User user);

    User findById(Long id);

    User findByEmail(String email);

    void deleteById(Long id);
}
