package com.aicareer.controller;

import com.aicareer.mapper.AgentRunMapper;
import com.aicareer.model.entity.AgentRun;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/agent-runs")
public class AgentRunController {

    private final AgentRunMapper agentRunMapper;

    public AgentRunController(AgentRunMapper agentRunMapper) {
        this.agentRunMapper = agentRunMapper;
    }

    @GetMapping("/recent")
    public ResponseEntity<List<AgentRun>> findRecent(
            @RequestParam(defaultValue = "20") int limit) {
        List<AgentRun> runs = agentRunMapper.findRecent(limit);
        return ResponseEntity.ok(runs);
    }
}
