# WaslaSerga Backend ↔ AI Service Integration API

## 📋 Executive Summary

This document defines the **complete, production-ready contract** for integration between the .NET Backend and Python AI Microservice for the WaslaSerga platform.

**Target Audience:** AI agents, Backend developers, Integration engineers

**Goal:** Enable implementation without requiring clarification or making assumptions.

## 🌐 Backend Base URL

```
https://wasla-v1.runasp.net
```

**Frontend-facing AI endpoints:**
```
POST https://wasla-v1.runasp.net/api/ai/chat
POST https://wasla-v1.runasp.net/api/ai/ingest
```

**AI Microservice Base URL (Internal):**
```json
{
  "AIService": {
    "BaseUrl": "https://f1e3-35-247-184-151.ngrok-free.app"
  }
}
```

---

## 🏗️ Architecture Overview

```
┌─────────────┐      JWT       ┌──────────────┐     HTTP/JSON    ┌─────────────┐
│   Frontend  │ ───────────────→ │   .NET       │ ───────────────→ │   Python    │
│   (React)   │                  │   Backend    │                  │   AI        │
│             │ ←─────────────── │   (API)      │ ←─────────────── │   Service   │
└─────────────┘    Result<T>     └──────────────┘    JSON Payload  └─────────────┘
                                      │
                                      │ SQL
                                      ▼
                                ┌──────────────┐
                                │   SQL Server │
                                │   Database   │
                                └──────────────┘
```

---

## 🔐 Authentication & Security

### JWT Token Flow

| Step | Action | Details |
|------|--------|---------|
| 1 | Frontend sends request | `Authorization: Bearer {jwt_token}` |
| 2 | Backend validates JWT | Standard JWT validation (Issuer, Audience, Expiry) |
| 3 | Backend extracts UserId | From JWT claims: `sub` (user identifier) |
| 4 | Backend forwards to AI | Includes UserId in request payload |
| 5 | AI processes & responds | Returns JSON with actions/data |
| 6 | Backend enriches response | Fetches DB data if needed |
| 7 | Backend returns Result<T> | Standard result pattern to frontend |

### AI Service Authentication

```csharp
// Backend → AI Service Authentication
public class AIServiceClient
{
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl;
    
    public AIServiceClient(IConfiguration config, HttpClient httpClient)
    {
        _baseUrl = config["AIService:BaseUrl"]!; // From appsettings.json
        _httpClient = httpClient;
        _httpClient.BaseAddress = new Uri(_baseUrl);
        // Future: Add API key header if AI service requires auth
        // _httpClient.DefaultRequestHeaders.Add("X-API-Key", config["AIService:ApiKey"]);
    }
}
```

---

## 📦 Data Models

### Enums (Defined in `Common/Enums/AIEnums.cs`)

```csharp
// AI Feature Types with Point Costs
public enum AIFeatureType
{
    ChatAssistant = 1,           // Free
    CVImprovement = 2,           // 20 points
    FileSummarization = 3,       // 10 points
    ProfileEnhancement = 4,      // 15 points
    ProposalGeneration = 5       // 25 points
}

// AI Request Processing Status
public enum AIRequestStatus
{
    Pending = 0,
    Processing = 1,
    Success = 2,
    Failed = 3,
    Cancelled = 4,
    InsufficientPoints = 5
}
```

### AI Action Types (Backend → Frontend Actions)

```csharp
public enum AIActionType
{
    DISPLAY_TEXT = 1,           // Show text response
    RECOMMEND_HELPERS = 2,      // Show helper recommendations
    NAVIGATE_TO_PAGE = 3,       // Navigate to specific page
    SHOW_TASK_FORM = 4,         // Open task creation form
    SHOW_SERVICE_DETAILS = 5,  // Display service information
    GENERATE_DOCUMENT = 6,       // Generated document ready
    REQUEST_MORE_INFO = 7,      // Ask user for clarification
    CONFIRM_ACTION = 8          // Request user confirmation
}
```

---

## 🔹 Endpoint 1: AI Chat

### Endpoint Specification

| Property | Value |
|----------|-------|
| **URL** | `POST /api/ai/chat` |
| **Method** | POST |
| **Authentication** | JWT Required |
| **Content-Type** | `application/json` |
| **Purpose** | Main AI assistant endpoint for natural language interactions |

### Request Structure (Frontend → Backend)

```json
{
  "message": "I need a React developer to build an e-commerce website",
  "conversationId": "conv-uuid-optional",  // Optional: for continuing conversation
  "context": {
    "currentPage": "/helpers",
    "selectedHelperId": null,
    "selectedTaskId": null
  }
}
```

### Backend Processing Logic (Pre-AI)

```csharp
public class AIChatHandler
{
    public async Task<Result<AIChatResponse>> Handle(AIChatRequest request)
    {
        // 1. Extract UserId from JWT
        var userId = _currentUserService.GetUserId();
        
        // 2. Check/record AI usage (points deduction if applicable)
        var featureType = AIFeatureType.ChatAssistant; // Free
        var usageRecord = await _aiUsageService.RecordUsageAsync(userId, featureType);
        
        // 3. Build User Context for AI
        var userContext = await BuildUserContextAsync(userId);
        
        // 4. Build System Context (available helpers, categories, etc.)
        var systemContext = await BuildSystemContextAsync();
        
        // 5. Send to AI Service
        var aiPayload = new AIChatPayload
        {
            UserMessage = request.Message,
            UserContext = userContext,
            SystemContext = systemContext,
            ConversationHistory = await GetConversationHistory(request.ConversationId)
        };
        
        // 6. Call AI Microservice
        var aiResponse = await _aiServiceClient.SendChatAsync(aiPayload);
        
        // 7. Process AI Actions (enrich with DB data if needed)
        var processedResponse = await ProcessAIActionsAsync(aiResponse, userId);
        
        // 8. Return Result<T>
        return Result.Success(processedResponse);
    }
}
```

### Backend → AI Service Request

**Endpoint:** `POST {AIService:BaseUrl}/chat`

```json
{
  "userId": "user-guid-from-jwt",
  "message": "I need a React developer to build an e-commerce website",
  "userContext": {
    "name": "John Doe",
    "role": "Seeker",
    "skills": [],
    "location": "Cairo, Egypt",
    "completedTasks": 5,
    "memberSince": "2024-01-15"
  },
  "systemContext": {
    "availableCategories": ["Technical", "Design", "Marketing"],
    "topHelpers": [
      {
        "id": 1,
        "name": "Jane Smith",
        "skills": ["React", "Node.js", "E-commerce"],
        "hourlyRate": 500,
        "rating": 4.8
      }
    ],
    "recentTasks": [
      {
        "id": 1,
        "title": "E-commerce website",
        "category": "Technical"
      }
    ]
  },
  "conversationHistory": [
    {
      "role": "user",
      "content": "Previous message",
      "timestamp": "2024-01-15T10:00:00Z"
    },
    {
      "role": "assistant",
      "content": "Previous response",
      "timestamp": "2024-01-15T10:01:00Z"
    }
  ],
  "metadata": {
    "featureType": "ChatAssistant",
    "timestamp": "2024-01-15T10:30:00Z",
    "clientVersion": "1.0.0"
  }
}
```

### AI Service → Backend Response

```json
{
  "responseText": "I found 3 excellent React developers who specialize in e-commerce. Would you like to see their profiles or shall I help you create a task posting?",
  "actions": [
    {
      "type": "RECOMMEND_HELPERS",
      "priority": 1,
      "payload": {
        "helperIds": [1, 5, 12],
        "reasoning": "These helpers have React and e-commerce experience with high ratings",
        "filters": {
          "skills": ["React", "E-commerce"],
          "minRating": 4.5
        }
      }
    },
    {
      "type": "SHOW_TASK_FORM",
      "priority": 2,
      "payload": {
        "preFilledData": {
          "title": "React E-commerce Developer Needed",
          "category": "Technical",
          "description": "Looking for an experienced React developer to build an e-commerce website"
        }
      }
    }
  ],
  "generatedDocs": [],
  "conversationId": "conv-uuid-generated",
  "metadata": {
    "processingTimeMs": 1250,
    "modelVersion": "gpt-4",
    "confidence": 0.92
  }
}
```

### Backend Post-Processing Logic

```csharp
private async Task<AIChatResponse> ProcessAIActionsAsync(AIResponse aiResponse, string userId)
{
    var response = new AIChatResponse
    {
        ResponseText = aiResponse.ResponseText,
        ConversationId = aiResponse.ConversationId,
        Metadata = aiResponse.Metadata
    };
    
    foreach (var action in aiResponse.Actions.OrderBy(a => a.Priority))
    {
        switch (action.Type)
        {
            case AIActionType.RECOMMEND_HELPERS:
                // Enrich helper IDs with full data from DB
                var helperIds = action.Payload.GetProperty("helperIds").Deserialize<int[]>();
                var helpers = await _helperRepo.GetAll()
                    .Where(h => helperIds.Contains(h.Id))
                    .Include(h => h.User)
                    .Include(h => h.HelperSkills)
                        .ThenInclude(hs => hs.Skill)
                    .ToListAsync();
                
                response.Actions.Add(new ProcessedAction
                {
                    Type = action.Type,
                    Payload = new { helpers }
                });
                break;
                
            case AIActionType.SHOW_TASK_FORM:
            case AIActionType.NAVIGATE_TO_PAGE:
            case AIActionType.DISPLAY_TEXT:
                // Pass through without enrichment
                response.Actions.Add(new ProcessedAction
                {
                    Type = action.Type,
                    Payload = action.Payload
                });
                break;
                
            default:
                // Unknown action - log warning, skip gracefully
                _logger.LogWarning("Unknown AI action type: {ActionType}", action.Type);
                break;
        }
    }
    
    return response;
}
```

### Backend → Frontend Response (Result<AIChatResponse>)

```json
{
  "isSuccess": true,
  "hasData": true,
  "data": {
    "responseText": "I found 3 excellent React developers who specialize in e-commerce. Would you like to see their profiles or shall I help you create a task posting?",
    "conversationId": "conv-uuid-123",
    "actions": [
      {
        "type": "RECOMMEND_HELPERS",
        "payload": {
          "helpers": [
            {
              "id": 1,
              "userId": "user-guid-1",
              "name": "Jane Smith",
              "profilePictureUrl": "https://cdn.example.com/avatar1.jpg",
              "headline": "React & E-commerce Specialist",
              "skills": ["React", "Node.js", "E-commerce", "Stripe"],
              "hourlyRate": 500.00,
              "averageRating": 4.8,
              "totalReviewsCount": 25,
              "isAvailable": true,
              "profileUrl": "/helpers/1"
            }
          ],
          "reasoning": "These helpers have React and e-commerce experience with high ratings"
        }
      },
      {
        "type": "SHOW_TASK_FORM",
        "payload": {
          "preFilledData": {
            "title": "React E-commerce Developer Needed",
            "category": "Technical",
            "description": "Looking for an experienced React developer to build an e-commerce website"
          }
        }
      }
    ],
    "suggestions": [
      "Show me their portfolios",
      "Create a task now",
      "What are their rates?"
    ],
    "metadata": {
      "processingTimeMs": 1250,
      "modelVersion": "gpt-4",
      "confidence": 0.92
    }
  }
}
```

---

## 🔹 Endpoint 2: AI Ingest

### Endpoint Specification

| Property | Value |
|----------|-------|
| **URL** | `POST /api/ai/ingest` |
| **Method** | POST |
| **Authentication** | JWT Required |
| **Content-Type** | `multipart/form-data` |
| **Purpose** | Ingest documents/files for AI processing (CV summarization, contract analysis, etc.) |

### Request Structure (Frontend → Backend)

```http
POST /api/ai/ingest
Content-Type: multipart/form-data
Authorization: Bearer {jwt_token}

------Boundary123
Content-Disposition: form-data; name="file"; filename="resume.pdf"
Content-Type: application/pdf

[Binary PDF data]
------Boundary123
Content-Disposition: form-data; name="featureType"

CVImprovement
------Boundary123
Content-Disposition: form-data; name="metadata"

{"language": "en", "detailLevel": "detailed"}
------Boundary123--
```

### Ingest Feature Types

| FeatureType | Points Cost | Description | Supported Formats |
|-------------|-------------|-------------|-------------------|
| `CVImprovement` | 20 | Analyze and improve CV/resume | PDF, DOCX, TXT |
| `FileSummarization` | 10 | Summarize any document | PDF, DOCX, TXT, MD |
| `ProfileEnhancement` | 15 | Generate profile improvements | PDF, DOCX, TXT |
| `ProposalGeneration` | 25 | Generate project proposals | PDF, DOCX, TXT |

### Backend Processing Logic (Pre-AI)

```csharp
public class AIIngestHandler
{
    public async Task<Result<AIIngestResponse>> Handle(AIIngestRequest request)
    {
        // 1. Extract UserId from JWT
        var userId = _currentUserService.GetUserId();
        
        // 2. Validate and parse feature type
        if (!Enum.TryParse<AIFeatureType>(request.FeatureType, out var featureType))
        {
            return Result.Failure<AIIngestResponse>(Error.Validation("AI.InvalidFeatureType", "Invalid feature type specified"));
        }
        
        // 3. Check user has sufficient points (except free features)
        var pointsRequired = GetPointsCost(featureType);
        if (pointsRequired > 0)
        {
            var hasPoints = await _pointsService.HasSufficientPointsAsync(userId, pointsRequired);
            if (!hasPoints)
            {
                await _aiUsageService.RecordUsageAsync(userId, featureType, AIRequestStatus.InsufficientPoints);
                return Result.Failure<AIIngestResponse>(
                    Error.Conflict("AI.InsufficientPoints", $"This feature requires {pointsRequired} points. Please earn more points."));
            }
        }
        
        // 4. Validate file
        var validation = await ValidateFileAsync(request.File, featureType);
        if (!validation.IsSuccess)
        {
            return Result.Failure<AIIngestResponse>(validation.Error);
        }
        
        // 5. Save file temporarily
        var tempFilePath = await _fileService.SaveTempAsync(request.File);
        
        // 6. Extract text content (if needed based on file type)
        var extractedText = await ExtractTextAsync(tempFilePath, request.File.ContentType);
        
        // 7. Record usage as Processing
        var usageRecord = await _aiUsageService.RecordUsageAsync(userId, featureType, AIRequestStatus.Processing, 
            inputLength: extractedText?.Length ?? request.File.Length);
        
        // 8. Build User Context
        var userContext = await BuildUserContextAsync(userId);
        
        // 9. Send to AI Service
        try
        {
            var aiPayload = new AIIngestPayload
            {
                UserId = userId,
                FeatureType = featureType,
                FileContent = extractedText, // or send file URL for AI to fetch
                FileMetadata = new FileMetadata
                {
                    FileName = request.File.FileName,
                    ContentType = request.File.ContentType,
                    Size = request.File.Length
                },
                UserContext = userContext,
                Options = request.Metadata
            };
            
            var aiResponse = await _aiServiceClient.SendIngestAsync(aiPayload);
            
            // 10. Deduct points (on success)
            if (pointsRequired > 0)
            {
                await _pointsService.DeductPointsAsync(userId, pointsRequired, $"AI {featureType}");
            }
            
            // 11. Update usage record as Success
            await _aiUsageService.UpdateStatusAsync(usageRecord.Id, AIRequestStatus.Success, 
                outputLength: aiResponse.GeneratedContent?.Length);
            
            // 12. Cleanup temp file
            _fileService.DeleteTemp(tempFilePath);
            
            return Result.Success(new AIIngestResponse
            {
                GeneratedContent = aiResponse.GeneratedContent,
                Suggestions = aiResponse.Suggestions,
                Actions = aiResponse.Actions,
                UsageId = usageRecord.Id,
                PointsDeducted = pointsRequired
            });
        }
        catch (Exception ex)
        {
            // Update usage record as Failed
            await _aiUsageService.UpdateStatusAsync(usageRecord.Id, AIRequestStatus.Failed, errorMessage: ex.Message);
            _fileService.DeleteTemp(tempFilePath);
            throw;
        }
    }
}
```

### Backend → AI Service Request

**Endpoint:** `POST {AIService:BaseUrl}/ingest`

```json
{
  "userId": "user-guid-from-jwt",
  "featureType": "CVImprovement",
  "fileContent": "Extracted text from PDF...",
  "fileMetadata": {
    "fileName": "resume.pdf",
    "contentType": "application/pdf",
    "size": 245760,
    "pageCount": 2
  },
  "userContext": {
    "name": "John Doe",
    "role": "Helper",
    "currentHeadline": "Software Developer",
    "currentBio": "...",
    "skills": ["C#", "React"],
    "experience": "5 years"
  },
  "options": {
    "language": "en",
    "detailLevel": "detailed",
    "targetSections": ["Summary", "Experience", "Skills"]
  },
  "metadata": {
    "timestamp": "2024-01-15T10:30:00Z",
    "clientVersion": "1.0.0",
    "usageId": 123
  }
}
```

### AI Service → Backend Response

```json
{
  "generatedContent": {
    "improvedCV": "# John Doe - Senior Full Stack Developer\n\n## Professional Summary\nResults-driven software developer with 5+ years...",
    "sections": {
      "summary": "Compelling new summary...",
      "experience": "Enhanced experience descriptions...",
      "skills": "Organized skills section..."
    },
    "improvements": [
      {
        "section": "Summary",
        "original": "Software developer with 5 years experience",
        "improved": "Results-driven Full Stack Developer with 5+ years...",
        "reason": "More specific and impact-oriented"
      }
    ]
  },
  "suggestions": [
    "Add metrics to your project descriptions",
    "Include certifications section",
    "Highlight leadership experience"
  ],
  "actions": [
    {
      "type": "GENERATE_DOCUMENT",
      "priority": 1,
      "payload": {
        "documentType": "CV",
        "format": "markdown",
        "downloadUrl": "/api/ai/download/{usageId}",
        "content": "Full improved CV content"
      }
    },
    {
      "type": "UPDATE_PROFILE",
      "priority": 2,
      "payload": {
        "suggestedHeadline": "Senior Full Stack Developer",
        "suggestedBio": "...",
        "suggestedSkills": ["C#", "React", "Node.js", "Azure"]
      }
    }
  ],
  "confidence": 0.88,
  "processingTimeMs": 3500
}
```

### Backend → Frontend Response (Result<AIIngestResponse>)

```json
{
  "isSuccess": true,
  "hasData": true,
  "data": {
    "generatedContent": {
      "improvedCV": "# John Doe - Senior Full Stack Developer\n\n## Professional Summary...",
      "sections": { ... },
      "improvements": [ ... ]
    },
    "suggestions": [
      "Add metrics to your project descriptions",
      "Include certifications section",
      "Highlight leadership experience"
    ],
    "actions": [
      {
        "type": "GENERATE_DOCUMENT",
        "payload": {
          "documentType": "CV",
          "format": "markdown",
          "downloadUrl": "/api/ai/download/123",
          "content": "Full improved CV content"
        }
      },
      {
        "type": "UPDATE_PROFILE",
        "payload": {
          "suggestedHeadline": "Senior Full Stack Developer",
          "suggestedBio": "...",
          "suggestedSkills": ["C#", "React", "Node.js", "Azure"]
        }
      }
    ],
    "usageId": 123,
    "pointsDeducted": 20,
    "remainingPoints": 180,
    "metadata": {
      "confidence": 0.88,
      "processingTimeMs": 3500
    }
  }
}
```

---

## 🔹 Helper Recommendation Flow (AI-Triggered)

### Overview

When the AI service determines that helper recommendations are appropriate, it returns a `RECOMMEND_HELPERS` action. The backend enriches this with full helper data from the database.

### Flow Diagram

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend  │────→│   Backend    │────→│   AI Service │────→│   Backend    │
│             │     │              │     │              │     │   (Enrich)   │
└─────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                    │
                                                                    │ SQL
                                                                    ▼
                                                             ┌──────────────┐
                                                             │   Database   │
                                                             │  (Helpers)   │
                                                             └──────┬───────┘
                                                                    │
                                                                    │ Data
                                                                    ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend  │←────│   Backend    │←────│  Processed   │←────│   Backend    │
│  (Display)  │     │  (Response)  │     │   Actions    │     │   (Enrich)   │
└─────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

### AI Action: RECOMMEND_HELPERS

**AI Service Returns:**
```json
{
  "type": "RECOMMEND_HELPERS",
  "priority": 1,
  "payload": {
    "helperIds": [1, 5, 12],
    "reasoning": "These helpers have React and e-commerce experience",
    "filters": {
      "skills": ["React", "E-commerce"],
      "minRating": 4.5,
      "availableOnly": true
    },
    "recommendationContext": "User asked for React e-commerce developer"
  }
}
```

**Backend Enrichment Logic:**
```csharp
private async Task<ProcessedAction> EnrichHelperRecommendationsAsync(AIAction action, string userId)
{
    var payload = action.Payload;
    var helperIds = payload.GetProperty("helperIds").Deserialize<int[]>();
    var reasoning = payload.GetProperty("reasoning").GetString();
    
    // Fetch full helper details from database
    var helpers = await _helperRepo.GetAll()
        .Where(h => helperIds.Contains(h.Id) && !h.IsDeleted && h.IsAvailable)
        .Include(h => h.User)
        .Include(h => h.HelperSkills)
            .ThenInclude(hs => hs.Skill)
        .Include(h => h.HelperServices)
        .Select(h => new HelperRecommendationDto
        {
            Id = h.Id,
            UserId = h.UserId,
            Name = h.User.Name,
            ProfilePictureUrl = h.User.ProfilePictureUrl,
            Headline = h.Headline,
            Bio = h.Bio,
            Location = h.Location,
            HourlyRate = h.HourlyRate,
            IsAvailable = h.IsAvailable,
            IsVerified = h.IsVerified,
            AverageRating = h.AverageRating,
            TotalReviewsCount = h.TotalReviewsCount,
            CompletedTasksCount = h.CompletedTasksCount,
            Skills = h.HelperSkills.Select(s => s.Skill.Name).ToList(),
            TopServices = h.HelperServices.Take(3).Select(s => new ServiceDto
            {
                Id = s.Id,
                Title = s.Title,
                Price = s.Price
            }).ToList(),
            ProfileUrl = $"/helpers/{h.Id}",
            MatchScore = CalculateMatchScore(h, payload.GetProperty("filters"))
        })
        .ToListAsync();
    
    // Order by the original AI recommendation order
    var orderedHelpers = helperIds
        .Select(id => helpers.FirstOrDefault(h => h.Id == id))
        .Where(h => h != null)
        .ToList();
    
    return new ProcessedAction
    {
        Type = AIActionType.RECOMMEND_HELPERS,
        Payload = new
        {
            Helpers = orderedHelpers,
            Reasoning = reasoning,
            TotalMatches = orderedHelpers.Count,
            UserLocation = await GetUserLocationAsync(userId),
            SuggestedNextSteps = new[]
            {
                "View full profile",
                "Send message",
                "Book consultation"
            }
        }
    };
}
```

### Frontend Response Structure

```json
{
  "type": "RECOMMEND_HELPERS",
  "payload": {
    "helpers": [
      {
        "id": 1,
        "userId": "user-guid-1",
        "name": "Jane Smith",
        "profilePictureUrl": "https://cdn.example.com/avatar1.jpg",
        "headline": "React & E-commerce Specialist",
        "bio": "Expert in building scalable e-commerce solutions with React and Node.js",
        "location": "Cairo, Egypt",
        "hourlyRate": 500.00,
        "isAvailable": true,
        "isVerified": true,
        "averageRating": 4.9,
        "totalReviewsCount": 42,
        "completedTasksCount": 35,
        "skills": ["React", "Node.js", "E-commerce", "Stripe", "MongoDB"],
        "topServices": [
          { "id": 1, "title": "E-commerce Website", "price": 8000.00 },
          { "id": 2, "title": "React Development", "price": 500.00 }
        ],
        "profileUrl": "/helpers/1",
        "matchScore": 0.95,
        "matchReasons": ["React expert", "E-commerce experience", "High rating"]
      }
    ],
    "reasoning": "These helpers have React and e-commerce experience with high ratings",
    "totalMatches": 3,
    "userLocation": "Cairo, Egypt",
    "suggestedNextSteps": ["View full profile", "Send message", "Book consultation"]
  }
}
```

---

## 🔧 Error Handling Specification

### AI Timeout Behavior

```csharp
// Configuration
public class AIServiceOptions
{
    public int TimeoutSeconds { get; set; } = 30;  // Default timeout
    public int MaxRetries { get; set; } = 2;       // Retry attempts
    public int CircuitBreakerThreshold { get; set; } = 5;  // Failures before opening circuit
    public int CircuitBreakerDurationSeconds { get; set; } = 60;  // Circuit open duration
}

// Implementation
public class AIServiceClient
{
    public async Task<AIResponse> SendChatAsync(AIChatPayload payload)
    {
        var retryCount = 0;
        while (retryCount <= _options.MaxRetries)
        {
            try
            {
                using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(_options.TimeoutSeconds));
                var response = await _httpClient.PostAsJsonAsync("/chat", payload, cts.Token);
                response.EnsureSuccessStatusCode();
                return await response.Content.ReadFromJsonAsync<AIResponse>(cts.Token);
            }
            catch (TaskCanceledException ex) when (ex.InnerException is TimeoutException)
            {
                retryCount++;
                if (retryCount > _options.MaxRetries)
                {
                    _logger.LogError("AI service timeout after {Retries} retries", _options.MaxRetries);
                    throw new AIServiceException("AI service is taking too long. Please try again later.");
                }
                await Task.Delay(TimeSpan.FromSeconds(Math.Pow(2, retryCount)));  // Exponential backoff
            }
        }
        throw new AIServiceException("Failed to get response from AI service");
    }
}
```

### AI Failure Fallback Response

When AI service fails or times out, backend returns a graceful fallback:

```json
{
  "isSuccess": true,  // Still success from backend perspective
  "hasData": true,
  "data": {
    "responseText": "I'm having trouble connecting to my AI services right now. Here are some popular helpers you might want to check out:",
    "conversationId": "fallback-conv-id",
    "actions": [
      {
        "type": "RECOMMEND_HELPERS",
        "payload": {
          "helpers": [ /* Top 3 helpers by rating from DB */ ],
          "reasoning": "Top-rated helpers (fallback mode)",
          "isFallback": true
        }
      }
    ],
    "suggestions": [
      "Show me all helpers",
      "Create a task instead",
      "Try again later"
    ],
    "metadata": {
      "isFallbackResponse": true,
      "aiError": "Timeout after 30s",
      "fallbackStrategy": "TopRatedHelpers"
    }
  }
}
```

### Invalid JSON Response Handling

```csharp
public async Task<AIResponse> ParseAIResponseAsync(HttpResponseMessage response)
{
    var content = await response.Content.ReadAsStringAsync();
    
    try
    {
        var aiResponse = JsonSerializer.Deserialize<AIResponse>(content, new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase
        });
        
        if (aiResponse == null)
        {
            throw new AIServiceException("AI service returned empty response");
        }
        
        // Validate required fields
        if (string.IsNullOrEmpty(aiResponse.ResponseText) && (aiResponse.Actions == null || !aiResponse.Actions.Any()))
        {
            _logger.LogWarning("AI response missing both responseText and actions");
        }
        
        return aiResponse;
    }
    catch (JsonException ex)
    {
        _logger.LogError(ex, "Failed to parse AI response: {Content}", content.Substring(0, 1000));
        
        // Return fallback response structure
        return new AIResponse
        {
            ResponseText = "I received an unexpected response. Let me help you in a different way.",
            Actions = new List<AIAction>
            {
                new AIAction
                {
                    Type = AIActionType.DISPLAY_TEXT,
                    Priority = 1,
                    Payload = JsonDocument.Parse("{\"message\": \"Please try again or contact support\"}").RootElement
                }
            },
            Metadata = new Dictionary<string, object>
            {
                ["parseError"] = ex.Message,
                ["isErrorResponse"] = true
            }
        };
    }
}
```

### Network Failure Strategy

```csharp
public class ResilientAIServiceClient
{
    private readonly HttpClient _httpClient;
    private readonly AsyncCircuitBreakerPolicy _circuitBreaker;
    private readonly AsyncRetryPolicy _retryPolicy;
    
    public ResilientAIServiceClient(HttpClient httpClient, AIServiceOptions options)
    {
        _httpClient = httpClient;
        
        // Circuit breaker: Stop calling if 5 failures in 60 seconds
        _circuitBreaker = Policy
            .Handle<HttpRequestException>()
            .Or<TimeoutException>()
            .Or<TaskCanceledException>()
            .CircuitBreakerAsync(
                options.CircuitBreakerThreshold,
                TimeSpan.FromSeconds(options.CircuitBreakerDurationSeconds),
                onBreak: (exception, duration) => 
                    _logger.LogError("AI service circuit broken for {Duration}s: {Exception}", duration, exception.Message),
                onReset: () => 
                    _logger.LogInformation("AI service circuit reset"));
        
        // Retry: 2 retries with exponential backoff
        _retryPolicy = Policy
            .Handle<HttpRequestException>()
            .Or<TimeoutException>()
            .Or<TaskCanceledException>()
            .WaitAndRetryAsync(
                options.MaxRetries,
                retryAttempt => TimeSpan.FromSeconds(Math.Pow(2, retryAttempt)),
                (exception, timeSpan, retryCount, context) =>
                    _logger.LogWarning("AI service call failed (attempt {Retry}): {Exception}. Retrying in {Delay}s...", 
                        retryCount, exception.Message, timeSpan.TotalSeconds));
    }
    
    public async Task<AIResponse> CallWithResilienceAsync(string endpoint, object payload)
    {
        return await _circuitBreaker.ExecuteAsync(async () =>
        {
            return await _retryPolicy.ExecuteAsync(async () =>
            {
                var response = await _httpClient.PostAsJsonAsync(endpoint, payload);
                response.EnsureSuccessStatusCode();
                return await response.Content.ReadFromJsonAsync<AIResponse>();
            });
        });
    }
}
```

---

## 📊 Complete Integration Flow: End-to-End Example

### Scenario: User asks for "React developer for e-commerce website"

#### Step 1: Frontend → Backend
```http
POST /api/ai/chat
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "message": "I need a React developer to build an e-commerce website",
  "context": {
    "currentPage": "/dashboard",
    "selectedHelperId": null
  }
}
```

#### Step 2: Backend Validation & Context Building
```csharp
// Backend extracts from JWT:
// - UserId: "user-abc-123"
// - Role: "Seeker"
// - Email: "john@example.com"

// Fetches user context from DB:
var user = await _userRepo.GetByIdAsync("user-abc-123");
var recentTasks = await _taskRepo.GetRecentByUserAsync("user-abc-123", 5);
var allHelpers = await _helperRepo.GetAvailableAsync();
```

#### Step 3: Backend → AI Service
```json
POST https://ai-service.ngrok.app/chat
Content-Type: application/json

{
  "userId": "user-abc-123",
  "message": "I need a React developer to build an e-commerce website",
  "userContext": {
    "name": "John Doe",
    "role": "Seeker",
    "location": "Cairo, Egypt",
    "completedTasks": 3,
    "memberSince": "2024-01-15",
    "skills": []
  },
  "systemContext": {
    "availableCategories": ["Technical", "Design", "Marketing"],
    "topHelpers": [
      {
        "id": 1,
        "name": "Jane Smith",
        "skills": ["React", "Node.js", "E-commerce"],
        "hourlyRate": 500,
        "rating": 4.8
      }
    ]
  },
  "conversationHistory": []
}
```

#### Step 4: AI Processing (Python Service)
```python
# Python AI Service Logic
class ChatProcessor:
    def process(self, request):
        # 1. Intent classification
        intent = self.classify_intent(request.message)
        # -> "seek_helper_for_task"
        
        # 2. Extract requirements
        requirements = self.extract_requirements(request.message)
        # -> {"skills": ["React"], "domain": "e-commerce"}
        
        # 3. Match helpers from context
        matched_helpers = self.match_helpers(
            request.system_context.top_helpers,
            requirements
        )
        
        # 4. Generate response
        return {
            "responseText": "I found 3 excellent React developers...",
            "actions": [
                {
                    "type": "RECOMMEND_HELPERS",
                    "priority": 1,
                    "payload": {
                        "helperIds": [matched_helpers[0].id, ...],
                        "reasoning": "...",
                        "filters": {...}
                    }
                }
            ]
        }
```

#### Step 5: AI → Backend Response
```json
{
  "responseText": "I found 3 excellent React developers who specialize in e-commerce. Would you like to see their profiles?",
  "actions": [
    {
      "type": "RECOMMEND_HELPERS",
      "priority": 1,
      "payload": {
        "helperIds": [1, 5, 12],
        "reasoning": "These helpers have React and e-commerce experience",
        "filters": {
          "skills": ["React", "E-commerce"],
          "minRating": 4.5
        }
      }
    },
    {
      "type": "SHOW_TASK_FORM",
      "priority": 2,
      "payload": {
        "preFilledData": {
          "title": "React E-commerce Developer Needed",
          "category": "Technical"
        }
      }
    }
  ],
  "conversationId": "conv-xyz-789",
  "metadata": {
    "processingTimeMs": 1250,
    "confidence": 0.92
  }
}
```

#### Step 6: Backend Enrichment
```csharp
// Backend fetches full helper data:
var helperIds = new[] { 1, 5, 12 };
var helpers = await _context.Helpers
    .Where(h => helperIds.Contains(h.Id))
    .Include(h => h.User)
    .Include(h => h.HelperSkills).ThenInclude(hs => hs.Skill)
    .ToListAsync();

// Maps to DTOs
var enrichedHelpers = helpers.Select(h => new HelperRecommendationDto { ... });
```

#### Step 7: Backend → Frontend (Final Response)
```json
{
  "isSuccess": true,
  "hasData": true,
  "data": {
    "responseText": "I found 3 excellent React developers who specialize in e-commerce. Would you like to see their profiles?",
    "conversationId": "conv-xyz-789",
    "actions": [
      {
        "type": "RECOMMEND_HELPERS",
        "payload": {
          "helpers": [
            {
              "id": 1,
              "name": "Jane Smith",
              "headline": "React & E-commerce Specialist",
              "skills": ["React", "Node.js", "E-commerce"],
              "hourlyRate": 500,
              "averageRating": 4.8,
              "profileUrl": "/helpers/1"
            }
          ],
          "reasoning": "These helpers have React and e-commerce experience",
          "suggestedNextSteps": ["View full profile", "Send message", "Book consultation"]
        }
      },
      {
        "type": "SHOW_TASK_FORM",
        "payload": {
          "preFilledData": {
            "title": "React E-commerce Developer Needed",
            "category": "Technical"
          }
        }
      }
    ],
    "suggestions": [
      "Show me their portfolios",
      "What are their rates?",
      "Book a consultation"
    ],
    "metadata": {
      "processingTimeMs": 1450,
      "modelVersion": "gpt-4",
      "confidence": 0.92
    }
  }
}
```

#### Step 8: Frontend Rendering
```typescript
// React component handles actions:
function ChatMessage({ response }) {
  return (
    <div>
      <p>{response.responseText}</p>
      
      {/* Render Helper Cards */}
      {response.actions
        .filter(a => a.type === 'RECOMMEND_HELPERS')
        .map(action => (
          <HelperCards helpers={action.payload.helpers} />
        ))}
      
      {/* Show Suggested Quick Replies */}
      <QuickReplies suggestions={response.suggestions} />
    </div>
  );
}
```

---

## 📋 API Reference Summary

### Backend Endpoints (Frontend-Facing)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/ai/chat` | POST | JWT | Main AI chat interface |
| `/api/ai/ingest` | POST | JWT | File/document processing |

### Internal Endpoints (Backend → AI Microservice)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `{AIService:BaseUrl}/chat` | POST | Natural language processing |
| `{AIService:BaseUrl}/ingest` | POST | Document/file processing |

---

## 🛡️ Production Safety Checklist

### For AI Agents / Automated Systems

- [ ] **Never** send actual JWT tokens in example requests
- [ ] **Always** validate AI response structure before processing
- [ ] **Always** implement timeout and retry logic
- [ ] **Always** use circuit breaker for AI service calls
- [ ] **Never** expose AI service base URL publicly (use backend proxy)
- [ ] **Always** sanitize user input before sending to AI
- [ ] **Always** validate and escape AI-generated HTML/content
- [ ] **Always** log AI usage for monitoring and billing

### Data Safety

- [ ] User passwords **never** sent to AI service
- [ ] Financial data (wallet balance) **never** sent to AI service
- [ ] PII (phone, email) **only** sent when necessary for context
- [ ] File uploads **always** scanned for malware before processing
- [ ] AI-generated content **always** sanitized before display

---

## 🔧 Implementation Notes

### Required Services (Backend)

```csharp
// Required service registrations in DependencyInjection.cs
public static IServiceCollection AddAIServices(this IServiceCollection services, IConfiguration config)
{
    // AI HTTP Client with resilience policies
    services.AddHttpClient<IAIServiceClient, AIServiceClient>(client =>
    {
        client.BaseAddress = new Uri(config["AIService:BaseUrl"]!);
        client.Timeout = TimeSpan.FromSeconds(30);
    })
    .AddPolicyHandler(GetRetryPolicy())
    .AddPolicyHandler(GetCircuitBreakerPolicy());
    
    // AI-related services
    services.AddScoped<IAIUsageService, AIUsageService>();
    services.AddScoped<IAIContextBuilder, AIContextBuilder>();
    services.AddScoped<IAIResponseProcessor, AIResponseProcessor>();
    
    return services;
}
```

### Required Database Entity (Already Exists)

```csharp
// Entities/AI/AIUsage.cs (Already in codebase)
public class AIUsage : AuditableEntity  
{
    public int Id { get; set; }
    public string UserId { get; set; } = string.Empty;
    public AIFeatureType FeatureType { get; set; }
    public int PointsCost { get; set; }
    public int? InputLength { get; set; }
    public int? OutputLength { get; set; }
    public AIRequestStatus Status { get; set; } = AIRequestStatus.Success;
    public string? ErrorMessage { get; set; }
    public int? PointTransactionId { get; set; }
    public DateTime UsedAt { get; set; } = DateTime.UtcNow;
    
    public ApplicationUser User { get; set; } = default!;
    public PointTransaction? PointTransaction { get; set; }
}
```

---

## 📞 Support & Troubleshooting

### Common Error Codes

| Error Code | Description | Resolution |
|------------|-------------|------------|
| `AI.Timeout` | AI service didn't respond in time | Retry with exponential backoff |
| `AI.InvalidResponse` | AI returned malformed JSON | Log and return fallback response |
| `AI.InsufficientPoints` | User doesn't have enough points | Prompt user to earn more points |
| `AI.ServiceUnavailable` | Circuit breaker is open | Wait for circuit to reset (60s) |
| `AI.InvalidFeatureType` | Unknown feature type requested | Validate before sending |
| `AI.FileTooLarge` | Uploaded file exceeds limit | Limit: 10MB per file |
| `AI.InvalidFileType` | Unsupported file format | Allowed: PDF, DOCX, TXT, MD |

### Monitoring Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `ai_request_duration_seconds` | Time to process AI request | > 10s |
| `ai_requests_total` | Total AI requests | N/A |
| `ai_errors_total` | Failed AI requests | > 5% error rate |
| `ai_circuit_breaker_state` | Circuit breaker status | Open |
| `ai_points_deducted_total` | Points spent on AI | N/A |

---

## 📝 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-04-20 | Initial AI integration contract specification |

---

**Document Status:** Specification Ready for Implementation  
**Target Implementation:** .NET Backend + Python AI Microservice  
**Compliance:** Must follow existing Result Pattern, JWT authentication, and entity structures


