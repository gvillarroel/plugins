"""Static typed operation catalog, audited against the parser at build time.

Runtime operation dispatch never imports the parser or accepts argv.
"""

import json

OPERATIONS = json.loads(r'''
{
  "add_aha": {
    "cli_path": [
      "add",
      "aha"
    ],
    "defaults": {
      "base_url": null,
      "key": null,
      "limit": null,
      "token": null,
      "workspace": null
    },
    "handler": "knowledge.commands:cmd_add_aha_workspace",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "base_url": {
          "description": "Aha base URL.",
          "type": "string"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "limit": {
          "description": "Feature sync limit.",
          "type": "integer"
        },
        "token": {
          "description": "Token or credential key reference.",
          "type": "string"
        },
        "workspace": {
          "description": "Aha workspace or product identifier.",
          "type": "string"
        }
      },
      "required": [
        "workspace",
        "key"
      ],
      "type": "object"
    }
  },
  "add_arxiv": {
    "cli_path": [
      "add",
      "arxiv"
    ],
    "defaults": {
      "batch_size": 50,
      "if_missing": false,
      "key": null,
      "request_delay": 3.0,
      "sync": false,
      "url": null
    },
    "handler": "knowledge.commands:cmd_add_arxiv",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "batch_size": {
          "description": "Paper IDs per arXiv metadata request (1-200).",
          "type": "integer"
        },
        "if_missing": {
          "description": "Treat already registered canonical paper versions as successful no-ops.",
          "type": "boolean"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "request_delay": {
          "description": "Seconds to wait between arXiv sync requests in a batch.",
          "type": "number"
        },
        "sync": {
          "description": "Synchronize every supplied paper after registration.",
          "type": "boolean"
        },
        "url": {
          "description": "arXiv or alphaXiv paper URL. Repeatable.",
          "items": {
            "description": "arXiv or alphaXiv paper URL. Repeatable.",
            "type": "string"
          },
          "minItems": 1,
          "type": "array"
        }
      },
      "required": [
        "url",
        "key"
      ],
      "type": "object"
    }
  },
  "add_confluence": {
    "cli_path": [
      "add",
      "confluence"
    ],
    "defaults": {
      "base_url": null,
      "connect_timeout": null,
      "cql": null,
      "key": null,
      "limit": null,
      "max_pages": null,
      "max_retries": null,
      "max_retry_wait": null,
      "page_size": null,
      "space": null,
      "timeout": null,
      "token": null,
      "username": null,
      "workers": null
    },
    "handler": "knowledge.commands:cmd_add_confluence",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "base_url": {
          "description": "Confluence base URL.",
          "type": "string"
        },
        "connect_timeout": {
          "description": "Connection timeout in seconds (default: 10).",
          "type": "number"
        },
        "cql": {
          "description": "Persist a custom Confluence CQL filter for sync.",
          "type": "string"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "limit": {
          "description": "Legacy limit: inventory size for spaces, total cap for CQL.",
          "type": "integer"
        },
        "max_pages": {
          "description": "Total pages to sync; 0 means all pages (default: 0).",
          "type": "integer"
        },
        "max_retries": {
          "description": "Retries after the initial GET attempt (0-10; default: 4).",
          "type": "integer"
        },
        "max_retry_wait": {
          "description": "Maximum retry/cooldown wait per request in seconds (default: 120).",
          "type": "number"
        },
        "page_size": {
          "description": "Items per inventory request (1-250; default: 25).",
          "type": "integer"
        },
        "space": {
          "description": "Confluence space key.",
          "type": "string"
        },
        "timeout": {
          "description": "Read timeout per request in seconds (default: 60).",
          "type": "number"
        },
        "token": {
          "description": "Token or credential key reference.",
          "type": "string"
        },
        "username": {
          "description": "Username or credential key reference.",
          "type": "string"
        },
        "workers": {
          "description": "Concurrent page downloads (1-16; default: 4).",
          "type": "integer"
        }
      },
      "required": [
        "key"
      ],
      "type": "object"
    }
  },
  "add_github_repo": {
    "cli_path": [
      "add",
      "github-repo"
    ],
    "defaults": {
      "branch": null,
      "key": null,
      "repo_url": null
    },
    "handler": "knowledge.commands:cmd_add_github_repo",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "branch": {
          "description": "Branch to include. Repeatable.",
          "items": {
            "description": "Branch to include. Repeatable.",
            "type": "string"
          },
          "type": "array"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "repo_url": {
          "description": "Git repository URL.",
          "type": "string"
        }
      },
      "required": [
        "repo_url",
        "key"
      ],
      "type": "object"
    }
  },
  "add_google_releases": {
    "cli_path": [
      "add",
      "google-releases"
    ],
    "defaults": {
      "key": null,
      "url": null
    },
    "handler": "knowledge.commands:cmd_add_google_releases",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "url": {
          "description": "Google Cloud release notes feed URL.",
          "type": "string"
        }
      },
      "required": [
        "url",
        "key"
      ],
      "type": "object"
    }
  },
  "add_jira_project": {
    "cli_path": [
      "add",
      "jira-project"
    ],
    "defaults": {
      "base_url": null,
      "field": null,
      "jql": null,
      "key": null,
      "limit": null,
      "project": null,
      "token": null,
      "username": null
    },
    "handler": "knowledge.commands:cmd_add_jira_project",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "base_url": {
          "description": "Jira base URL.",
          "type": "string"
        },
        "field": {
          "description": "Field to request. Repeatable.",
          "items": {
            "description": "Field to request. Repeatable.",
            "type": "string"
          },
          "type": "array"
        },
        "jql": {
          "description": "Override default JQL.",
          "type": "string"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "limit": {
          "description": "Issue sync limit.",
          "type": "integer"
        },
        "project": {
          "description": "Jira project key.",
          "type": "string"
        },
        "token": {
          "description": "Token or credential key reference.",
          "type": "string"
        },
        "username": {
          "description": "Username or credential key reference.",
          "type": "string"
        }
      },
      "required": [
        "project",
        "key"
      ],
      "type": "object"
    }
  },
  "add_key": {
    "cli_path": [
      "add",
      "key"
    ],
    "defaults": {
      "name": null
    },
    "handler": "knowledge.commands:cmd_add_key",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "description": "Knowledge key name.",
          "type": "string"
        }
      },
      "required": [
        "name"
      ],
      "type": "object"
    }
  },
  "add_servicenow": {
    "cli_path": [
      "add",
      "servicenow"
    ],
    "defaults": {
      "assignment_group": null,
      "base_url": null,
      "field": null,
      "key": null,
      "knowledge_base": null,
      "limit": 1000,
      "page_size": 100,
      "password": null,
      "query": null,
      "table": "incident",
      "token": null,
      "username": null
    },
    "handler": "knowledge.servicenow_commands:cmd_add_servicenow",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "assignment_group": {
          "description": "Exact assignment group sys_id; only for tickets.",
          "type": "string"
        },
        "base_url": {
          "description": "HTTPS instance origin; defaults to SERVICENOW_BASE_URL.",
          "type": "string"
        },
        "field": {
          "description": "Field to retrieve; repeatable. Identity fields are always included.",
          "items": {
            "description": "Field to retrieve; repeatable. Identity fields are always included.",
            "type": "string"
          },
          "type": "array"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "knowledge_base": {
          "description": "Exact kb_knowledge_base sys_id; only for kb_knowledge.",
          "type": "string"
        },
        "limit": {
          "description": "Maximum records per synchronization.",
          "type": "integer"
        },
        "page_size": {
          "description": "Records requested per page (1-100).",
          "type": "integer"
        },
        "password": {
          "description": "Password reference ($name or $env:NAME), never a literal secret.",
          "type": "string"
        },
        "query": {
          "description": "Encoded filter; no ^NQ, ^EQ, or JavaScript.",
          "type": "string"
        },
        "table": {
          "description": "ServiceNow table (default: incident).",
          "enum": [
            "incident",
            "problem",
            "change_request",
            "sc_task",
            "sc_req_item",
            "kb_knowledge"
          ],
          "type": "string"
        },
        "token": {
          "description": "Bearer token reference ($name or $env:NAME), instead of basic authentication.",
          "type": "string"
        },
        "username": {
          "description": "Instance username or credential reference.",
          "type": "string"
        }
      },
      "required": [
        "key"
      ],
      "type": "object"
    }
  },
  "add_site": {
    "cli_path": [
      "add",
      "site"
    ],
    "defaults": {
      "compact": false,
      "key": null,
      "max_depth": 1,
      "max_pages": 1,
      "source_id": null,
      "url": null
    },
    "handler": "knowledge.commands:cmd_add_site",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "compact": {
          "description": "Deprecated. Final Markdown-only site output is now the default layout.",
          "type": "boolean"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "max_depth": {
          "description": "Optional crawl depth.",
          "type": "integer"
        },
        "max_pages": {
          "description": "Optional page limit.",
          "type": "integer"
        },
        "source_id": {
          "description": "Optional stable source id.",
          "type": "string"
        },
        "url": {
          "description": "Website URL.",
          "type": "string"
        }
      },
      "required": [
        "url",
        "key"
      ],
      "type": "object"
    }
  },
  "add_tv": {
    "cli_path": [
      "add",
      "tv"
    ],
    "defaults": {
      "action_command": null,
      "description": null,
      "key": null,
      "name": null,
      "preview_command": null,
      "source_command": null,
      "source_display": null
    },
    "handler": "knowledge.commands:cmd_add_television",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "action_command": {
          "description": "Optional command for the default open action.",
          "type": "string"
        },
        "description": {
          "description": "Channel description.",
          "type": "string"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "name": {
          "description": "Television channel name. Omit it to install the bundled cable files.",
          "type": "string"
        },
        "preview_command": {
          "description": "Optional Television preview command.",
          "type": "string"
        },
        "source_command": {
          "description": "Television source command.",
          "type": "string"
        },
        "source_display": {
          "description": "Optional Television source display template.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "add_video": {
    "cli_path": [
      "add",
      "video"
    ],
    "defaults": {
      "key": null,
      "language": null,
      "url": null
    },
    "handler": "knowledge.commands:cmd_add_video",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "language": {
          "description": "Preferred transcript language. Repeatable.",
          "items": {
            "description": "Preferred transcript language. Repeatable.",
            "type": "string"
          },
          "type": "array"
        },
        "url": {
          "description": "Video URL or local path.",
          "type": "string"
        }
      },
      "required": [
        "url",
        "key"
      ],
      "type": "object"
    }
  },
  "browse_aha": {
    "cli_path": [
      "browse",
      "aha"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_aha",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Restrict to a knowledge key.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_arxiv": {
    "cli_path": [
      "browse",
      "arxiv"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_arxiv",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Restrict to a knowledge key.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_by_key": {
    "cli_path": [
      "browse",
      "by-key"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_extended:cmd_browse_by_key",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_by_type": {
    "cli_path": [
      "browse",
      "by-type"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_extended:cmd_browse_by_type",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_commands": {
    "cli_path": [
      "browse",
      "commands"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_extended:cmd_browse_commands",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_confluence": {
    "cli_path": [
      "browse",
      "confluence"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_confluence",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Restrict to a knowledge key.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_confluence_pages": {
    "cli_path": [
      "browse",
      "confluence-pages"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "selected_row": null,
      "space": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_confluence_pages",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "selected_row": {
          "description": "Television row for drill-in from spaces channel.",
          "type": "string"
        },
        "space": {
          "description": "Confluence space key.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_confluence_spaces": {
    "cli_path": [
      "browse",
      "confluence-spaces"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_commands:cmd_browse_confluence_spaces",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_crossref": {
    "cli_path": [
      "browse",
      "crossref"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_extended:cmd_browse_crossref",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_files": {
    "cli_path": [
      "browse",
      "files"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null,
      "query": null
    },
    "handler": "knowledge.browse_extended:cmd_browse_files",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Restrict to a knowledge key.",
          "type": "string"
        },
        "query": {
          "description": "Full-text search query.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_follow": {
    "cli_path": [
      "browse",
      "follow"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_commands:cmd_browse_follow",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_follow_open": {
    "cli_path": [
      "browse",
      "follow-open"
    ],
    "defaults": {
      "selected_row": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_follow_launch",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "selected_row": {
          "description": "Television row text.",
          "type": "string"
        }
      },
      "required": [
        "selected_row"
      ],
      "type": "object"
    }
  },
  "browse_follow_url": {
    "cli_path": [
      "browse",
      "follow-url"
    ],
    "defaults": {
      "selected_row": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_follow_open",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "selected_row": {
          "description": "Television row text.",
          "type": "string"
        }
      },
      "required": [
        "selected_row"
      ],
      "type": "object"
    }
  },
  "browse_github": {
    "cli_path": [
      "browse",
      "github"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_github",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Restrict to a knowledge key.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_github_activity": {
    "cli_path": [
      "browse",
      "github-activity"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "repo": null,
      "selected_row": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_github_activity",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "repo": {
          "description": "Repository in owner/repo format.",
          "type": "string"
        },
        "selected_row": {
          "description": "Full Television row text to derive the repository from when drilling in from another channel.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_jira": {
    "cli_path": [
      "browse",
      "jira"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_jira",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Restrict to a knowledge key.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_jira_projects": {
    "cli_path": [
      "browse",
      "jira-projects"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_commands:cmd_browse_jira_projects",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_key_sources": {
    "cli_path": [
      "browse",
      "key-sources"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null
    },
    "handler": "knowledge.browse_extended:cmd_browse_key_sources",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        }
      },
      "required": [
        "key"
      ],
      "type": "object"
    }
  },
  "browse_local": {
    "cli_path": [
      "browse",
      "local"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null,
      "type": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_local",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Restrict to a knowledge key.",
          "type": "string"
        },
        "type": {
          "description": "Restrict to a source type.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_papers": {
    "cli_path": [
      "browse",
      "papers"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_extended:cmd_browse_papers",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_recent": {
    "cli_path": [
      "browse",
      "recent"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "limit": 50
    },
    "handler": "knowledge.browse_extended:cmd_browse_recent",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "limit": {
          "description": "Max items.",
          "type": "integer"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_releases": {
    "cli_path": [
      "browse",
      "releases"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_releases",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Restrict to a knowledge key.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_repo_files": {
    "cli_path": [
      "browse",
      "repo-files"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "repo": null
    },
    "handler": "knowledge.browse_extended:cmd_browse_repo_files",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "repo": {
          "description": "Filter by repo name.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_repos": {
    "cli_path": [
      "browse",
      "repos"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_extended:cmd_browse_repos",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_servicenow": {
    "cli_path": [
      "browse",
      "servicenow"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null,
      "type": "servicenow"
    },
    "handler": "knowledge.browse_commands:cmd_browse_local",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Exact result row to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_sites": {
    "cli_path": [
      "browse",
      "sites"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_sites",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Restrict to a knowledge key.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_source_files": {
    "cli_path": [
      "browse",
      "source-files"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null,
      "source_id": null
    },
    "handler": "knowledge.browse_extended:cmd_browse_source_files",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "source_id": {
          "description": "Source ID.",
          "type": "string"
        }
      },
      "required": [
        "key",
        "source_id"
      ],
      "type": "object"
    }
  },
  "browse_stale": {
    "cli_path": [
      "browse",
      "stale"
    ],
    "defaults": {
      "days": 7,
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_extended:cmd_browse_stale",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "days": {
          "description": "Consider stale after N days.",
          "type": "integer"
        },
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_stats": {
    "cli_path": [
      "browse",
      "stats"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_extended:cmd_browse_stats",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_timeline": {
    "cli_path": [
      "browse",
      "timeline"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_extended:cmd_browse_timeline",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_unsynced": {
    "cli_path": [
      "browse",
      "unsynced"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.browse_extended:cmd_browse_unsynced",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "browse_videos": {
    "cli_path": [
      "browse",
      "videos"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null
    },
    "handler": "knowledge.browse_commands:cmd_browse_videos",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Restrict to a knowledge key.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "del": {
    "cli_path": [
      "del"
    ],
    "defaults": {
      "key": null,
      "source_id": null
    },
    "handler": "knowledge.commands:cmd_delete_source",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "source_id": {
          "description": "Registered source id.",
          "type": "string"
        }
      },
      "required": [
        "key",
        "source_id"
      ],
      "type": "object"
    }
  },
  "export": {
    "cli_path": [
      "export"
    ],
    "defaults": {
      "key": null
    },
    "handler": "knowledge.commands:cmd_export",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Restrict export to a single knowledge key.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "import": {
    "cli_path": [
      "import"
    ],
    "defaults": {
      "archive": null
    },
    "handler": "knowledge.commands:cmd_import",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "archive": {
          "description": "Zip archive path.",
          "type": "string"
        }
      },
      "required": [
        "archive"
      ],
      "type": "object"
    }
  },
  "init": {
    "cli_path": [
      "init"
    ],
    "defaults": {},
    "handler": "knowledge.commands:cmd_init",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {},
      "required": [],
      "type": "object"
    }
  },
  "list_credentials": {
    "cli_path": [
      "list",
      "credentials"
    ],
    "defaults": {},
    "handler": "knowledge.commands:cmd_key_list",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {},
      "required": [],
      "type": "object"
    }
  },
  "list_keys": {
    "cli_path": [
      "list",
      "keys"
    ],
    "defaults": {
      "entry": null,
      "format": "json"
    },
    "handler": "knowledge.commands:cmd_list_keys",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview when using --format television-preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "list_sources": {
    "cli_path": [
      "list",
      "sources"
    ],
    "defaults": {
      "entry": null,
      "format": "json",
      "key": null,
      "type": null
    },
    "handler": "knowledge.commands:cmd_list_collection_sources",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "entry": {
          "description": "Entry to preview when using --format television-preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Restrict to a single knowledge key.",
          "type": "string"
        },
        "type": {
          "description": "Restrict to a single source type.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "search_arxiv": {
    "cli_path": [
      "search",
      "arxiv"
    ],
    "defaults": {
      "additional_query": null,
      "entry": null,
      "format": "json",
      "max_results": 10,
      "only_unregistered": false,
      "published_after": null,
      "query": null,
      "query_file": null,
      "registered_key": null,
      "request_delay": 3.0,
      "sort_by": "relevance",
      "sort_order": "descending",
      "start": 0
    },
    "handler": "knowledge.commands:cmd_search_arxiv",
    "mutates": false,
    "path_parameters": [
      "query_file"
    ],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "additional_query": {
          "description": "Add another query lane. Repeatable; lanes are searched sequentially and deduplicated.",
          "items": {
            "description": "Add another query lane. Repeatable; lanes are searched sequentially and deduplicated.",
            "type": "string"
          },
          "type": "array"
        },
        "entry": {
          "description": "Entry title to preview when using --format television-preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format. Use television variants when wiring the command into tv.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "max_results": {
          "description": "Maximum number of results.",
          "type": "integer"
        },
        "only_unregistered": {
          "description": "Return only exact versions absent from --registered-key.",
          "type": "boolean"
        },
        "published_after": {
          "description": "Keep papers published strictly after this ISO-8601 timestamp.",
          "type": "string"
        },
        "query": {
          "description": "arXiv search_query expression or plain text.",
          "type": "string"
        },
        "query_file": {
          "description": "UTF-8 file containing one query lane per line; blank lines and # comments are ignored.",
          "type": "string"
        },
        "registered_key": {
          "description": "Annotate results with exact-version and any-version registration state for this key.",
          "type": "string"
        },
        "request_delay": {
          "description": "Seconds to wait between query lanes.",
          "type": "number"
        },
        "sort_by": {
          "description": "Sort field supported by the arXiv API.",
          "enum": [
            "relevance",
            "lastUpdatedDate",
            "submittedDate"
          ],
          "type": "string"
        },
        "sort_order": {
          "description": "Sort direction supported by the arXiv API.",
          "enum": [
            "ascending",
            "descending"
          ],
          "type": "string"
        },
        "start": {
          "description": "Starting result offset.",
          "type": "integer"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "search_brave": {
    "cli_path": [
      "search",
      "brave"
    ],
    "defaults": {
      "accept": null,
      "api_version": null,
      "cache_control": null,
      "count": 10,
      "country": null,
      "enable_rich_callback": null,
      "entry": null,
      "extra_snippets": null,
      "format": "json",
      "freshness": null,
      "goggles": null,
      "include_fetch_metadata": null,
      "loc_city": null,
      "loc_country": null,
      "loc_lat": null,
      "loc_long": null,
      "loc_postal_code": null,
      "loc_state": null,
      "loc_state_name": null,
      "loc_timezone": null,
      "offset": 0,
      "operators": null,
      "query": null,
      "result_filter": null,
      "safesearch": null,
      "search_lang": null,
      "spellcheck": null,
      "summary": null,
      "text_decorations": null,
      "ui_lang": null,
      "units": null,
      "user_agent": null
    },
    "handler": "knowledge.commands:cmd_search_brave",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "accept": {
          "description": "Accept header to send to Brave.",
          "enum": [
            "application/json",
            "*/*"
          ],
          "type": "string"
        },
        "api_version": {
          "description": "Explicit Brave API version header.",
          "type": "string"
        },
        "cache_control": {
          "description": "Cache-Control header for Brave requests.",
          "enum": [
            "no-cache"
          ],
          "type": "string"
        },
        "count": {
          "description": "Maximum number of Brave results.",
          "type": "integer"
        },
        "country": {
          "description": "Country code for regional results, for example US.",
          "type": "string"
        },
        "enable_rich_callback": {
          "description": "Enable Brave rich callback support.",
          "type": "boolean"
        },
        "entry": {
          "description": "Entry title to preview when using --format television-preview.",
          "type": "string"
        },
        "extra_snippets": {
          "description": "Request additional alternate snippets.",
          "type": "boolean"
        },
        "format": {
          "description": "Output format. Use television variants when wiring the command into tv.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "freshness": {
          "description": "Freshness filter such as pd, pw, pm, py, or YYYY-MM-DDtoYYYY-MM-DD.",
          "type": "string"
        },
        "goggles": {
          "description": "Goggle URL or inline definition. Repeatable.",
          "items": {
            "description": "Goggle URL or inline definition. Repeatable.",
            "type": "string"
          },
          "type": "array"
        },
        "include_fetch_metadata": {
          "description": "Include fetch metadata in the response.",
          "type": "boolean"
        },
        "loc_city": {
          "description": "Client city for local results.",
          "type": "string"
        },
        "loc_country": {
          "description": "Client country code for local results.",
          "type": "string"
        },
        "loc_lat": {
          "description": "Client latitude for local results.",
          "type": "number"
        },
        "loc_long": {
          "description": "Client longitude for local results.",
          "type": "number"
        },
        "loc_postal_code": {
          "description": "Client postal code for local results.",
          "type": "string"
        },
        "loc_state": {
          "description": "Client state or region code for local results.",
          "type": "string"
        },
        "loc_state_name": {
          "description": "Client state or region name for local results.",
          "type": "string"
        },
        "loc_timezone": {
          "description": "Client IANA timezone for local results.",
          "type": "string"
        },
        "offset": {
          "description": "Page offset to skip before returning results.",
          "type": "integer"
        },
        "operators": {
          "description": "Apply Brave search operators found in the query.",
          "type": "boolean"
        },
        "query": {
          "description": "Text to search on the web.",
          "type": "string"
        },
        "result_filter": {
          "description": "Result types to include. Repeatable.",
          "items": {
            "description": "Result types to include. Repeatable.",
            "enum": [
              "discussions",
              "faq",
              "infobox",
              "news",
              "query",
              "summarizer",
              "videos",
              "web",
              "locations"
            ],
            "type": "string"
          },
          "type": "array"
        },
        "safesearch": {
          "description": "Adult-content filtering level.",
          "enum": [
            "off",
            "moderate",
            "strict"
          ],
          "type": "string"
        },
        "search_lang": {
          "description": "Language code for search results, for example en.",
          "type": "string"
        },
        "spellcheck": {
          "description": "Enable Brave spell correction.",
          "type": "boolean"
        },
        "summary": {
          "description": "Enable summary generation for summarizer results.",
          "type": "boolean"
        },
        "text_decorations": {
          "description": "Include Brave text decoration markers in snippets.",
          "type": "boolean"
        },
        "ui_lang": {
          "description": "Preferred UI language in the response, for example en-US.",
          "type": "string"
        },
        "units": {
          "description": "Measurement units for result formatting.",
          "enum": [
            "imperial",
            "metric"
          ],
          "type": "string"
        },
        "user_agent": {
          "description": "User-Agent header for Brave requests.",
          "type": "string"
        }
      },
      "required": [
        "query"
      ],
      "type": "object"
    }
  },
  "search_confluence": {
    "cli_path": [
      "search",
      "confluence"
    ],
    "defaults": {
      "cql": null,
      "created_after": null,
      "created_before": null,
      "cursor": null,
      "entry": null,
      "format": "json",
      "knowledge_key": null,
      "label": null,
      "limit": 25,
      "query": null,
      "space": null,
      "text_contains": null,
      "title_contains": null,
      "type": null,
      "updated_after": null,
      "updated_before": null
    },
    "handler": "knowledge.commands:cmd_search_confluence",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "cql": {
          "description": "Override the generated CQL query.",
          "type": "string"
        },
        "created_after": {
          "description": "Restrict to content created after this ISO-8601 timestamp.",
          "type": "string"
        },
        "created_before": {
          "description": "Restrict to content created before this ISO-8601 timestamp.",
          "type": "string"
        },
        "cursor": {
          "description": "Cursor token from a previous response.",
          "type": "string"
        },
        "entry": {
          "description": "Entry to preview when using --format television-preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "knowledge_key": {
          "description": "Restrict to one knowledge key.",
          "type": "string"
        },
        "label": {
          "description": "Restrict by label. Repeatable.",
          "items": {
            "description": "Restrict by label. Repeatable.",
            "type": "string"
          },
          "type": "array"
        },
        "limit": {
          "description": "Maximum number of results per source.",
          "type": "integer"
        },
        "query": {
          "description": "Free-text query string.",
          "type": "string"
        },
        "space": {
          "description": "Restrict the search to one Confluence space.",
          "type": "string"
        },
        "text_contains": {
          "description": "Filter by body text.",
          "type": "string"
        },
        "title_contains": {
          "description": "Filter by title text.",
          "type": "string"
        },
        "type": {
          "description": "Restrict by Confluence content type.",
          "type": "string"
        },
        "updated_after": {
          "description": "Restrict to content updated after this ISO-8601 timestamp.",
          "type": "string"
        },
        "updated_before": {
          "description": "Restrict to content updated before this ISO-8601 timestamp.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "search_jira": {
    "cli_path": [
      "search",
      "jira"
    ],
    "defaults": {
      "assignee": null,
      "created_after": null,
      "created_before": null,
      "entry": null,
      "expand": null,
      "field": null,
      "fields_by_keys": false,
      "format": "json",
      "issue_type": null,
      "jql": null,
      "knowledge_key": null,
      "limit": 25,
      "next_page_token": null,
      "order_by": null,
      "project": null,
      "property": null,
      "query": null,
      "reporter": null,
      "status": null,
      "updated_after": null,
      "updated_before": null
    },
    "handler": "knowledge.commands:cmd_search_jira",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "assignee": {
          "description": "Restrict by assignee.",
          "type": "string"
        },
        "created_after": {
          "description": "Restrict to issues created after this ISO-8601 timestamp.",
          "type": "string"
        },
        "created_before": {
          "description": "Restrict to issues created before this ISO-8601 timestamp.",
          "type": "string"
        },
        "entry": {
          "description": "Entry to preview when using --format television-preview.",
          "type": "string"
        },
        "expand": {
          "description": "Expand value to request. Repeatable.",
          "items": {
            "description": "Expand value to request. Repeatable.",
            "type": "string"
          },
          "type": "array"
        },
        "field": {
          "description": "Field to request. Repeatable.",
          "items": {
            "description": "Field to request. Repeatable.",
            "type": "string"
          },
          "type": "array"
        },
        "fields_by_keys": {
          "description": "Ask Jira to interpret fields by keys.",
          "type": "boolean"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "issue_type": {
          "description": "Restrict by issue type. Repeatable.",
          "items": {
            "description": "Restrict by issue type. Repeatable.",
            "type": "string"
          },
          "type": "array"
        },
        "jql": {
          "description": "Explicit JQL to execute.",
          "type": "string"
        },
        "knowledge_key": {
          "description": "Restrict to one knowledge key.",
          "type": "string"
        },
        "limit": {
          "description": "Maximum number of results per source.",
          "type": "integer"
        },
        "next_page_token": {
          "description": "Enhanced-search pagination token.",
          "type": "string"
        },
        "order_by": {
          "description": "JQL ORDER BY expression fragment. Repeatable.",
          "items": {
            "description": "JQL ORDER BY expression fragment. Repeatable.",
            "type": "string"
          },
          "type": "array"
        },
        "project": {
          "description": "Restrict to one Jira project.",
          "type": "string"
        },
        "property": {
          "description": "Entity property to request. Repeatable.",
          "items": {
            "description": "Entity property to request. Repeatable.",
            "type": "string"
          },
          "type": "array"
        },
        "query": {
          "description": "Free-text query used to build JQL.",
          "type": "string"
        },
        "reporter": {
          "description": "Restrict by reporter.",
          "type": "string"
        },
        "status": {
          "description": "Restrict by Jira status. Repeatable.",
          "items": {
            "description": "Restrict by Jira status. Repeatable.",
            "type": "string"
          },
          "type": "array"
        },
        "updated_after": {
          "description": "Restrict to issues updated after this ISO-8601 timestamp.",
          "type": "string"
        },
        "updated_before": {
          "description": "Restrict to issues updated before this ISO-8601 timestamp.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "search_servicenow": {
    "cli_path": [
      "search",
      "servicenow"
    ],
    "defaults": {
      "assignment_group": null,
      "base_url": null,
      "entry": null,
      "field": null,
      "format": "json",
      "key": null,
      "knowledge_base": null,
      "limit": 25,
      "offset": 0,
      "password": null,
      "query": null,
      "source_id": null,
      "table": null,
      "text": null,
      "token": null,
      "username": null
    },
    "handler": "knowledge.servicenow_commands:cmd_search_servicenow",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "assignment_group": {
          "description": "Exact assignment group sys_id; only for tickets.",
          "type": "string"
        },
        "base_url": {
          "description": "HTTPS instance origin; defaults to SERVICENOW_BASE_URL.",
          "type": "string"
        },
        "entry": {
          "description": "Exact result row to preview.",
          "type": "string"
        },
        "field": {
          "description": "Field to retrieve; repeatable. Identity fields are always included.",
          "items": {
            "description": "Field to retrieve; repeatable. Identity fields are always included.",
            "type": "string"
          },
          "type": "array"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Use a registered ServiceNow source on this knowledge key.",
          "type": "string"
        },
        "knowledge_base": {
          "description": "Exact kb_knowledge_base sys_id; only for kb_knowledge.",
          "type": "string"
        },
        "limit": {
          "description": "Maximum records to return.",
          "type": "integer"
        },
        "offset": {
          "description": "Offset from a previous next_offset result.",
          "type": "integer"
        },
        "password": {
          "description": "Password reference ($name or $env:NAME), never a literal secret.",
          "type": "string"
        },
        "query": {
          "description": "Encoded filter; no ^NQ, ^EQ, or JavaScript.",
          "type": "string"
        },
        "source_id": {
          "description": "Select one exact registered source; requires --key.",
          "type": "string"
        },
        "table": {
          "description": "ServiceNow table (default: incident).",
          "enum": [
            "incident",
            "problem",
            "change_request",
            "sc_task",
            "sc_req_item",
            "kb_knowledge"
          ],
          "type": "string"
        },
        "text": {
          "description": "Literal text to find in short_description.",
          "type": "string"
        },
        "token": {
          "description": "Bearer token reference ($name or $env:NAME), instead of basic authentication.",
          "type": "string"
        },
        "username": {
          "description": "Instance username or credential reference.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "servicenow_create_ticket": {
    "cli_path": [
      "servicenow",
      "create-ticket"
    ],
    "defaults": {
      "assignment_group": null,
      "base_url": null,
      "caller_id": null,
      "correlation_id": null,
      "description": null,
      "description_file": null,
      "dry_run": false,
      "impact": null,
      "key": null,
      "password": null,
      "short_description": null,
      "source_id": null,
      "token": null,
      "urgency": null,
      "username": null
    },
    "handler": "knowledge.servicenow_commands:cmd_create_servicenow_ticket",
    "mutates": true,
    "path_parameters": [
      "description_file"
    ],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "assignment_group": {
          "description": "Assignment group sys_id.",
          "type": "string"
        },
        "base_url": {
          "description": "HTTPS instance origin; defaults to SERVICENOW_BASE_URL.",
          "type": "string"
        },
        "caller_id": {
          "description": "Caller sys_id, when required by the instance.",
          "type": "string"
        },
        "correlation_id": {
          "description": "External reference to identify this request; not an idempotency guarantee.",
          "type": "string"
        },
        "description": {
          "description": "Incident description.",
          "type": "string"
        },
        "description_file": {
          "description": "UTF-8 incident description file.",
          "type": "string"
        },
        "dry_run": {
          "description": "Preview the POST without resolving secrets or accessing the network.",
          "type": "boolean"
        },
        "impact": {
          "description": "Impact: 1 high, 2 medium, 3 low.",
          "enum": [
            "1",
            "2",
            "3"
          ],
          "type": "string"
        },
        "key": {
          "description": "Use a registered ServiceNow source on this knowledge key.",
          "type": "string"
        },
        "password": {
          "description": "Password reference ($name or $env:NAME), never a literal secret.",
          "type": "string"
        },
        "short_description": {
          "description": "Incident summary.",
          "type": "string"
        },
        "source_id": {
          "description": "Select one exact registered source; requires --key.",
          "type": "string"
        },
        "token": {
          "description": "Bearer token reference ($name or $env:NAME), instead of basic authentication.",
          "type": "string"
        },
        "urgency": {
          "description": "Urgency: 1 high, 2 medium, 3 low.",
          "enum": [
            "1",
            "2",
            "3"
          ],
          "type": "string"
        },
        "username": {
          "description": "Instance username or credential reference.",
          "type": "string"
        }
      },
      "required": [
        "short_description"
      ],
      "type": "object"
    }
  },
  "servicenow_knowledge_bases": {
    "cli_path": [
      "servicenow",
      "knowledge-bases"
    ],
    "defaults": {
      "base_url": null,
      "entry": null,
      "format": "json",
      "key": null,
      "limit": 100,
      "offset": 0,
      "password": null,
      "source_id": null,
      "token": null,
      "username": null
    },
    "handler": "knowledge.servicenow_commands:cmd_servicenow_knowledge_bases",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "base_url": {
          "description": "HTTPS instance origin; defaults to SERVICENOW_BASE_URL.",
          "type": "string"
        },
        "entry": {
          "description": "Exact result row to preview.",
          "type": "string"
        },
        "format": {
          "description": "Output format.",
          "enum": [
            "json",
            "television",
            "television-preview"
          ],
          "type": "string"
        },
        "key": {
          "description": "Use a registered ServiceNow source on this knowledge key.",
          "type": "string"
        },
        "limit": {
          "description": "Maximum knowledge bases to return.",
          "type": "integer"
        },
        "offset": {
          "description": "Offset from a previous result.",
          "type": "integer"
        },
        "password": {
          "description": "Password reference ($name or $env:NAME), never a literal secret.",
          "type": "string"
        },
        "source_id": {
          "description": "Select one exact registered source; requires --key.",
          "type": "string"
        },
        "token": {
          "description": "Bearer token reference ($name or $env:NAME), instead of basic authentication.",
          "type": "string"
        },
        "username": {
          "description": "Instance username or credential reference.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "servicenow_read_ticket": {
    "cli_path": [
      "servicenow",
      "read-ticket"
    ],
    "defaults": {
      "base_url": null,
      "identifier": null,
      "key": null,
      "password": null,
      "source_id": null,
      "table": null,
      "token": null,
      "username": null
    },
    "handler": "knowledge.servicenow_commands:cmd_read_servicenow_ticket",
    "mutates": false,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "base_url": {
          "description": "HTTPS instance origin; defaults to SERVICENOW_BASE_URL.",
          "type": "string"
        },
        "identifier": {
          "description": "Ticket number (for example INC0010001) or sys_id.",
          "type": "string"
        },
        "key": {
          "description": "Use a registered ServiceNow source on this knowledge key.",
          "type": "string"
        },
        "password": {
          "description": "Password reference ($name or $env:NAME), never a literal secret.",
          "type": "string"
        },
        "source_id": {
          "description": "Select one exact registered source; requires --key.",
          "type": "string"
        },
        "table": {
          "description": "Ticket table (default: incident or registered table).",
          "enum": [
            "incident",
            "problem",
            "change_request",
            "sc_task",
            "sc_req_item"
          ],
          "type": "string"
        },
        "token": {
          "description": "Bearer token reference ($name or $env:NAME), instead of basic authentication.",
          "type": "string"
        },
        "username": {
          "description": "Instance username or credential reference.",
          "type": "string"
        }
      },
      "required": [
        "identifier"
      ],
      "type": "object"
    }
  },
  "set_credential": {
    "cli_path": [
      "set",
      "credential"
    ],
    "defaults": {
      "name": null,
      "value": null
    },
    "handler": "knowledge.commands:cmd_key_set",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "description": "Credential name.",
          "type": "string"
        },
        "value": {
          "description": "Credential value.",
          "type": "string"
        }
      },
      "required": [
        "name",
        "value"
      ],
      "type": "object"
    }
  },
  "sync": {
    "cli_path": [
      "sync"
    ],
    "defaults": {
      "key": null,
      "match_value": null,
      "source_type": null
    },
    "handler": "knowledge.commands:cmd_sync",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Restrict sync to a single knowledge key.",
          "type": "string"
        }
      },
      "required": [],
      "type": "object"
    }
  },
  "sync_aha": {
    "cli_path": [
      "sync",
      "aha"
    ],
    "defaults": {
      "key": null,
      "match_value": null,
      "source_type": "aha",
      "workspace": null
    },
    "handler": "knowledge.commands:cmd_sync",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "workspace": {
          "description": "Aha workspace or product.",
          "type": "string"
        }
      },
      "required": [
        "workspace",
        "key"
      ],
      "type": "object"
    }
  },
  "sync_arxiv": {
    "cli_path": [
      "sync",
      "arxiv"
    ],
    "defaults": {
      "key": null,
      "match_value": null,
      "source_type": "arxiv",
      "url": null
    },
    "handler": "knowledge.commands:cmd_sync",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "url": {
          "description": "arXiv URL.",
          "type": "string"
        }
      },
      "required": [
        "url",
        "key"
      ],
      "type": "object"
    }
  },
  "sync_confluence": {
    "cli_path": [
      "sync",
      "confluence"
    ],
    "defaults": {
      "connect_timeout": null,
      "key": null,
      "match_value": null,
      "max_pages": null,
      "max_retries": null,
      "max_retry_wait": null,
      "page_size": null,
      "refresh": false,
      "source_type": "confluence",
      "space": null,
      "timeout": null,
      "workers": null
    },
    "handler": "knowledge.commands:cmd_sync",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "connect_timeout": {
          "description": "Connection timeout in seconds (default: 10).",
          "type": "number"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "max_pages": {
          "description": "Total pages to sync; 0 means all pages (default: 0).",
          "type": "integer"
        },
        "max_retries": {
          "description": "Retries after the initial GET attempt (0-10; default: 4).",
          "type": "integer"
        },
        "max_retry_wait": {
          "description": "Maximum retry/cooldown wait per request in seconds (default: 120).",
          "type": "number"
        },
        "page_size": {
          "description": "Items per inventory request (1-250; default: 25).",
          "type": "integer"
        },
        "refresh": {
          "description": "Ignore cached bodies and download every selected page.",
          "type": "boolean"
        },
        "space": {
          "description": "Restrict sync to one Confluence space key.",
          "type": "string"
        },
        "timeout": {
          "description": "Read timeout per request in seconds (default: 60).",
          "type": "number"
        },
        "workers": {
          "description": "Concurrent page downloads (1-16; default: 4).",
          "type": "integer"
        }
      },
      "required": [
        "key"
      ],
      "type": "object"
    }
  },
  "sync_github_repo": {
    "cli_path": [
      "sync",
      "github-repo"
    ],
    "defaults": {
      "branch": null,
      "key": null,
      "match_value": null,
      "repo_url": null,
      "source_type": "github"
    },
    "handler": "knowledge.commands:cmd_sync",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "branch": {
          "description": "Optional branch filters.",
          "items": {
            "description": "Optional branch filters.",
            "type": "string"
          },
          "type": "array"
        },
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "repo_url": {
          "description": "Git repository URL.",
          "type": "string"
        }
      },
      "required": [
        "repo_url",
        "key"
      ],
      "type": "object"
    }
  },
  "sync_google_releases": {
    "cli_path": [
      "sync",
      "google-releases"
    ],
    "defaults": {
      "key": null,
      "match_value": null,
      "source_type": "google_releases",
      "url": null
    },
    "handler": "knowledge.commands:cmd_sync",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "url": {
          "description": "Google Cloud release notes feed URL.",
          "type": "string"
        }
      },
      "required": [
        "url",
        "key"
      ],
      "type": "object"
    }
  },
  "sync_jira_project": {
    "cli_path": [
      "sync",
      "jira-project"
    ],
    "defaults": {
      "key": null,
      "match_value": null,
      "project": null,
      "source_type": "jira"
    },
    "handler": "knowledge.commands:cmd_sync",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "project": {
          "description": "Jira project key.",
          "type": "string"
        }
      },
      "required": [
        "project",
        "key"
      ],
      "type": "object"
    }
  },
  "sync_servicenow": {
    "cli_path": [
      "sync",
      "servicenow"
    ],
    "defaults": {
      "key": null,
      "match_value": null,
      "source_id": null,
      "source_type": null
    },
    "handler": "knowledge.servicenow_commands:cmd_sync_servicenow",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "source_id": {
          "description": "Sync one exact registration instead of all ServiceNow sources on the key.",
          "type": "string"
        }
      },
      "required": [
        "key"
      ],
      "type": "object"
    }
  },
  "sync_site": {
    "cli_path": [
      "sync",
      "site"
    ],
    "defaults": {
      "key": null,
      "match_value": null,
      "source_type": "site",
      "url": null
    },
    "handler": "knowledge.commands:cmd_sync",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "url": {
          "description": "Website URL.",
          "type": "string"
        }
      },
      "required": [
        "url",
        "key"
      ],
      "type": "object"
    }
  },
  "sync_television": {
    "cli_path": [
      "sync",
      "television"
    ],
    "defaults": {
      "key": null,
      "match_value": null,
      "name": null,
      "source_type": "television"
    },
    "handler": "knowledge.commands:cmd_sync",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "name": {
          "description": "Television channel name.",
          "type": "string"
        }
      },
      "required": [
        "name",
        "key"
      ],
      "type": "object"
    }
  },
  "sync_video": {
    "cli_path": [
      "sync",
      "video"
    ],
    "defaults": {
      "key": null,
      "match_value": null,
      "source_type": "video",
      "url": null
    },
    "handler": "knowledge.commands:cmd_sync",
    "mutates": true,
    "path_parameters": [],
    "schema": {
      "additionalProperties": false,
      "properties": {
        "key": {
          "description": "Knowledge key name.",
          "type": "string"
        },
        "url": {
          "description": "Video URL or local path.",
          "type": "string"
        }
      },
      "required": [
        "url",
        "key"
      ],
      "type": "object"
    }
  }
}
''')
