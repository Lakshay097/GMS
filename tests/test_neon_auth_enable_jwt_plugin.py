"""
Enable JWT plugin via Neon API
"""
import os
import httpx
import json
NEON_AUTH_BASE_URL = "https://ep-restless-moon-axra2khj.neonauth.c-4.us-east-2.aws.neon.tech/neondb/auth"

print("=" * 80)
print("NEON AUTH JWT PLUGIN ENABLEMENT")
print("=" * 80)

# Extract instance ID from base URL
instance_id = NEON_AUTH_BASE_URL.split("//")[1].split(".")[0]
print(f"Instance ID: {instance_id}")
print()

# Step 1: Get organization info first
print("STEP 1: Get organization info")
print("-" * 80)

try:
    org_url = "https://console.neon.tech/api/v2/orgs"
    headers = {"Authorization": f"Bearer {NEON_API_KEY}"}
    
    response = httpx.get(org_url, headers=headers, timeout=10)
    print(f"Orgs API Status: {response.status_code}")
    
    if response.status_code == 200:
        orgs_data = response.json()
        orgs = orgs_data.get('orgs', [])
        print(f"Found {len(orgs)} organizations")
        
        org_id = None
        for org in orgs:
            org_id = org.get('id')
            org_name = org.get('name', 'Unknown')
            print(f"Organization: {org_name} (ID: {org_id})")
            break  # Use first org
        
        if not org_id:
            print("[FAIL] No organizations found")
            exit(1)
    else:
        print(f"[FAIL] Failed to get orgs: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        exit(1)
        
except Exception as e:
    print(f"[FAIL] Error getting orgs: {str(e)}")
    import traceback
    traceback.print_exc()
    exit(1)

print()

# Step 2: Get projects with org_id
print("STEP 2: Get projects to find project_id")
print("-" * 80)

try:
    projects_url = f"https://console.neon.tech/api/v2/orgs/{org_id}/projects"
    response = httpx.get(projects_url, headers=headers, timeout=10)
    print(f"Projects API Status: {response.status_code}")
    
    if response.status_code == 200:
        projects_data = response.json()
        projects = projects_data.get('projects', [])
        print(f"Found {len(projects)} projects")
        
        # Look for project that contains our instance
        matching_project = None
        for project in projects:
            project_id = project.get('id')
            project_name = project.get('name', 'Unknown')
            print(f"Project: {project_name} (ID: {project_id})")
            
            # Check branches for this project
            branches_url = f"https://console.neon.tech/api/v2/projects/{project_id}/branches"
            branches_response = httpx.get(branches_url, headers=headers, timeout=10)
            
            if branches_response.status_code == 200:
                branches_data = branches_response.json()
                branches = branches_data.get('branches', [])
                
                for branch in branches:
                    branch_id = branch.get('id')
                    branch_name = branch.get('name', 'Unknown')
                    
                    # Check if this branch has Neon Auth with our instance
                    auth_url = branch.get('auth', {}).get('base_url', '')
                    if instance_id in auth_url:
                        print(f"  -> Found matching branch: {branch_name} (ID: {branch_id})")
                        print(f"  -> Auth URL: {auth_url}")
                        matching_project = {
                            'project_id': project_id,
                            'project_name': project_name,
                            'branch_id': branch_id,
                            'branch_name': branch_name
                        }
                        break
                
                if matching_project:
                    break
        
        if matching_project:
            print(f"\n[PASS] Found matching project and branch:")
            print(f"  Project: {matching_project['project_name']} ({matching_project['project_id']})")
            print(f"  Branch: {matching_project['branch_name']} ({matching_project['branch_id']})")
        else:
            print(f"[FAIL] Could not find project/branch for instance {instance_id}")
            exit(1)
    else:
        print(f"[FAIL] Failed to get projects: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        exit(1)
        
except Exception as e:
    print(f"[FAIL] Error getting projects: {str(e)}")
    import traceback
    traceback.print_exc()
    exit(1)

print()

# Step 3: Get current auth configuration
print("STEP 3: Get current auth configuration")
print("-" * 80)

try:
    auth_config_url = f"https://console.neon.tech/api/v2/projects/{matching_project['project_id']}/branches/{matching_project['branch_id']}/auth"
    response = httpx.get(auth_config_url, headers=headers, timeout=10)
    
    print(f"Auth Config Status: {response.status_code}")
    
    if response.status_code == 200:
        auth_config = response.json()
        print(f"Current Auth Config: {json.dumps(auth_config, indent=2)[:500]}...")
        
        # Check if JWT plugin is already enabled
        plugins = auth_config.get('plugins', [])
        jwt_enabled = any(plugin.get('type') == 'jwt' for plugin in plugins)
        
        if jwt_enabled:
            print(f"[INFO] JWT plugin already enabled")
        else:
            print(f"[INFO] JWT plugin not currently enabled")
    else:
        print(f"[FAIL] Failed to get auth config: {response.status_code}")
        print(f"Response: {response.text[:300]}")
        
except Exception as e:
    print(f"[FAIL] Error getting auth config: {str(e)}")
    import traceback
    traceback.print_exc()

print()

# Step 4: Try to enable JWT plugin
print("STEP 4: Enable JWT plugin")
print("-" * 80)

try:
    # Try to enable JWT plugin via auth config update
    auth_config_url = f"https://console.neon.tech/api/v2/projects/{matching_project['project_id']}/branches/{matching_project['branch_id']}/auth"
    
    # Update auth config to include JWT plugin
    update_payload = {
        "plugins": [
            {
                "type": "jwt",
                "enabled": true
            }
        ]
    }
    
    print(f"Attempting to enable JWT plugin via PATCH to auth config")
    patch_response = httpx.patch(auth_config_url, headers=headers, json=update_payload, timeout=10)
    print(f"PATCH Status: {patch_response.status_code}")
    
    if patch_response.status_code in [200, 201]:
        result = patch_response.json()
        print(f"[PASS] JWT plugin enable attempt successful")
        print(f"Result: {json.dumps(result, indent=2)[:400]}...")
    else:
        print(f"[FAIL] PATCH failed: {patch_response.status_code}")
        print(f"Response: {patch_response.text[:300]}")
        
        # Try alternative: enable via plugins endpoint
        print()
        print("Trying alternative: plugins endpoint")
        plugins_url = f"https://console.neon.tech/api/v2/projects/{matching_project['project_id']}/branches/{matching_project['branch_id']}/auth/plugins"
        
        # First try POST to add JWT plugin
        post_response = httpx.post(plugins_url, headers=headers, json={"type": "jwt", "enabled": True}, timeout=10)
        print(f"POST Plugins Status: {post_response.status_code}")
        
        if post_response.status_code in [200, 201]:
            result = post_response.json()
            print(f"[PASS] JWT plugin enable via POST successful")
            print(f"Result: {json.dumps(result, indent=2)[:400]}...")
        else:
            print(f"[FAIL] POST failed: {post_response.status_code}")
            print(f"Response: {post_response.text[:300]}")
    
except Exception as e:
    print(f"[FAIL] Error enabling JWT plugin: {str(e)}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("JWT PLUGIN ENABLEMENT ATTEMPT COMPLETE")
print("=" * 80)
print()
print("NEXT STEPS:")
print("1. Check Neon Console to verify plugin status")
print("2. Re-run JWT exchange test to verify functionality")
print("3. Test backend verification with obtained JWT")
