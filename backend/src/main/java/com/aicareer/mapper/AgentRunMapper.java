package com.aicareer.mapper;

import com.aicareer.model.entity.AgentRun;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface AgentRunMapper {

    void insert(AgentRun agentRun);

    AgentRun findById(Long id);

    List<AgentRun> findByAgentName(String agentName);

    List<AgentRun> findByUserId(Long userId);

    List<AgentRun> findRecent(@Param("limit") int limit);

    @Delete("DELETE FROM agent_runs WHERE user_id = #{userId}")
    int deleteByUserId(Long userId);
}
