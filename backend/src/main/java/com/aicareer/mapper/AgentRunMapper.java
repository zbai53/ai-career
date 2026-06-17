package com.aicareer.mapper;

import com.aicareer.model.entity.AgentRun;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface AgentRunMapper {

    void insert(AgentRun agentRun);

    AgentRun findById(Long id);

    List<AgentRun> findByAgentName(String agentName);

    List<AgentRun> findRecent(@Param("limit") int limit);
}
