package com.aicareer.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(session ->
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/health").permitAll()
                .requestMatchers("/api/resumes/**").permitAll()
                .requestMatchers("/api/jds/**").permitAll()
                .requestMatchers("/api/match/**").permitAll()
                .requestMatchers("/api/agent-runs/**").permitAll()
                .requestMatchers("/api/workflow/**").permitAll()
                .requestMatchers("/api/rewrite/**").permitAll()
                .requestMatchers("/api/interviews/**").permitAll()
                // TODO: lock down endpoints once authentication is implemented
                .anyRequest().permitAll()
            );
        return http.build();
    }
}
