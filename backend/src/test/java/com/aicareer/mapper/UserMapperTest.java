package com.aicareer.mapper;

import com.aicareer.model.entity.User;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@ActiveProfiles("test")
@Transactional
class UserMapperTest {

    @Autowired
    private UserMapper userMapper;

    private User buildUser(String emailSuffix) {
        User user = new User();
        user.setEmail("test" + emailSuffix + "@example.com");
        user.setPasswordHash("hashed_password");
        user.setName("Test User");
        return user;
    }

    @Test
    void test_insertAndFindById() {
        User user = buildUser("_findById");
        userMapper.insert(user);

        assertThat(user.getId()).isNotNull();

        User found = userMapper.findById(user.getId());

        assertThat(found).isNotNull();
        assertThat(found.getId()).isEqualTo(user.getId());
        assertThat(found.getEmail()).isEqualTo("test_findById@example.com");
        assertThat(found.getPasswordHash()).isEqualTo("hashed_password");
        assertThat(found.getName()).isEqualTo("Test User");
        assertThat(found.getCreatedAt()).isNotNull();
        assertThat(found.getUpdatedAt()).isNotNull();
    }

    @Test
    void test_findByEmail() {
        User user = buildUser("_byEmail");
        userMapper.insert(user);

        User found = userMapper.findByEmail("test_byEmail@example.com");

        assertThat(found).isNotNull();
        assertThat(found.getId()).isEqualTo(user.getId());
        assertThat(found.getEmail()).isEqualTo("test_byEmail@example.com");
    }

    @Test
    void test_findByEmail_notFound() {
        User found = userMapper.findByEmail("nobody@example.com");

        assertThat(found).isNull();
    }

    @Test
    void test_deleteById() {
        User user = buildUser("_delete");
        userMapper.insert(user);
        assertThat(userMapper.findById(user.getId())).isNotNull();

        userMapper.deleteById(user.getId());

        assertThat(userMapper.findById(user.getId())).isNull();
    }
}
