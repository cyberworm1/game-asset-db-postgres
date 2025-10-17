using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;
using UnityEditor;
using UnityEngine;

namespace GameAssetDb.Editor
{
    public class GameAssetDbWindow : EditorWindow
    {
        private const string ConfigFileName = "config.json";

        private static readonly JsonSerializerOptions ReadJsonOptions = new()
        {
            PropertyNameCaseInsensitive = true,
        };

        private static readonly JsonSerializerOptions WriteJsonOptions = new()
        {
            WriteIndented = true,
        };

        private Vector2 _scrollPosition;
        private string _searchQuery = string.Empty;
        private List<AssetSummary> _assets = new();
        private bool _isLoading;
        private string _statusMessage = string.Empty;
        private string _accessToken = string.Empty;
        private DateTime _tokenExpiryUtc = DateTime.MinValue;
        private GameAssetDbConfig _currentConfig;

        [MenuItem("Window/Game Asset DB")]
        public static void ShowWindow()
        {
            var window = GetWindow<GameAssetDbWindow>("Game Asset DB");
            window.Show();
        }

        private void OnEnable()
        {
            _ = RefreshAssetsAsync();
        }

        private async Task RefreshAssetsAsync()
        {
            if (_isLoading)
            {
                return;
            }

            _isLoading = true;
            _statusMessage = "Loading assets...";
            Repaint();

            try
            {
                _currentConfig = await LoadConfigAsync();
                if (string.IsNullOrWhiteSpace(_currentConfig.ProjectId))
                {
                    _assets = new List<AssetSummary>();
                    _statusMessage = "Set ProjectId in config.json to browse project assets.";
                    return;
                }

                await EnsureTokenAsync(_currentConfig);
                using var client = CreateHttpClient(_currentConfig);
                var route = $"projects/{_currentConfig.ProjectId}/assets";
                if (!string.IsNullOrWhiteSpace(_searchQuery))
                {
                    route += "?search=" + Uri.EscapeDataString(_searchQuery);
                }

                var response = await client.GetAsync(route);
                response.EnsureSuccessStatusCode();
                var json = await response.Content.ReadAsStringAsync();
                _assets = JsonSerializer.Deserialize<List<AssetSummary>>(json, ReadJsonOptions) ?? new List<AssetSummary>();
                _statusMessage = $"Loaded {_assets.Count} assets.";
            }
            catch (Exception ex)
            {
                _statusMessage = "Failed to load assets: " + ex.Message;
                Debug.LogError(ex);
            }
            finally
            {
                _isLoading = false;
                Repaint();
            }
        }

        private void OnGUI()
        {
            using (new EditorGUILayout.HorizontalScope())
            {
                _searchQuery = EditorGUILayout.TextField("Search", _searchQuery);
                if (GUILayout.Button("Refresh", GUILayout.Width(80)))
                {
                    _ = RefreshAssetsAsync();
                }
            }

            EditorGUILayout.Space();

            if (_isLoading)
            {
                EditorGUILayout.LabelField("Loading...");
                return;
            }

            _scrollPosition = EditorGUILayout.BeginScrollView(_scrollPosition);
            foreach (var asset in _assets)
            {
                EditorGUILayout.BeginVertical("box");
                EditorGUILayout.LabelField(asset.Name ?? "Unnamed Asset", EditorStyles.boldLabel);
                EditorGUILayout.LabelField("Type", asset.Type ?? "Unknown");
                EditorGUILayout.LabelField("Latest Version", asset.LatestVersion);

                if (asset.Metadata.ValueKind == JsonValueKind.Object)
                {
                    if (TryGetMetadataString(asset.Metadata, "description", out var description) && !string.IsNullOrEmpty(description))
                    {
                        EditorGUILayout.LabelField("Description", description);
                    }
                }

                EditorGUILayout.BeginHorizontal();
                if (GUILayout.Button("Import"))
                {
                    ImportAsset(asset);
                }

                if (TryGetMetadataString(asset.Metadata, "viewer_url", out var viewerUrl) && !string.IsNullOrEmpty(viewerUrl))
                {
                    if (GUILayout.Button("Open in Browser"))
                    {
                        Application.OpenURL(viewerUrl);
                    }
                }
                EditorGUILayout.EndHorizontal();
                EditorGUILayout.EndVertical();
            }
            EditorGUILayout.EndScrollView();

            EditorGUILayout.HelpBox(_statusMessage, MessageType.Info);
        }

        private void ImportAsset(AssetSummary asset)
        {
            _ = ImportAssetAsync(asset);
        }

        private async Task ImportAssetAsync(AssetSummary asset)
        {
            try
            {
                _statusMessage = $"Importing {asset.Name ?? asset.Id.ToString()}...";
                Repaint();
                if (_currentConfig == null)
                {
                    _currentConfig = await LoadConfigAsync();
                }

                if (_currentConfig == null || string.IsNullOrWhiteSpace(_currentConfig.ProjectId))
                {
                    _statusMessage = "Unable to import asset: ProjectId is missing.";
                    Repaint();
                    return;
                }

                await EnsureTokenAsync(_currentConfig);
                using var client = CreateHttpClient(_currentConfig);
                var response = await client.GetAsync($"assets/{asset.Id}");
                response.EnsureSuccessStatusCode();
                var json = await response.Content.ReadAsStringAsync();
                var detail = JsonSerializer.Deserialize<AssetDetail>(json, ReadJsonOptions);
                if (detail == null)
                {
                    throw new InvalidOperationException("Received empty asset payload.");
                }

                var assetFolder = Path.Combine("Assets", "GameAssetDb", SanitizeFolderName(detail.Name ?? detail.Id.ToString()));
                Directory.CreateDirectory(assetFolder);

                var metadataPath = Path.Combine(assetFolder, "asset.json");
                await File.WriteAllTextAsync(metadataPath, JsonSerializer.Serialize(detail, WriteJsonOptions), Encoding.UTF8);

                AssetDatabase.Refresh();
                _statusMessage = $"Imported {detail.Name ?? detail.Id.ToString()} into {assetFolder}.";
            }
            catch (Exception ex)
            {
                _statusMessage = "Failed to import asset: " + ex.Message;
                Debug.LogError(ex);
            }
            finally
            {
                Repaint();
            }
        }

        private async Task EnsureTokenAsync(GameAssetDbConfig config)
        {
            if (!string.IsNullOrEmpty(_accessToken) && DateTime.UtcNow < _tokenExpiryUtc.AddSeconds(-60))
            {
                return;
            }

            var payload = new TokenRequest
            {
                Username = config.Username,
                Password = config.Password,
            };

            if (string.IsNullOrWhiteSpace(payload.Username) || string.IsNullOrWhiteSpace(payload.Password))
            {
                throw new InvalidOperationException("Set username and password in config.json to authenticate with the service.");
            }

            using var client = new HttpClient
            {
                BaseAddress = new Uri(config.ApiBaseUrl.TrimEnd('/') + "/"),
            };

            var content = new StringContent(JsonSerializer.Serialize(payload, WriteJsonOptions), Encoding.UTF8, "application/json");
            var response = await client.PostAsync("auth/token", content);
            response.EnsureSuccessStatusCode();
            var json = await response.Content.ReadAsStringAsync();
            var token = JsonSerializer.Deserialize<TokenResponse>(json, ReadJsonOptions);
            if (token == null)
            {
                throw new InvalidOperationException("Token response was empty.");
            }

            _accessToken = token.AccessToken;
            _tokenExpiryUtc = DateTime.UtcNow.AddSeconds(token.ExpiresIn > 0 ? token.ExpiresIn : 3600);
        }

        private HttpClient CreateHttpClient(GameAssetDbConfig config)
        {
            var client = new HttpClient
            {
                BaseAddress = new Uri(config.ApiBaseUrl.TrimEnd('/') + "/"),
            };
            if (!string.IsNullOrEmpty(_accessToken))
            {
                client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", _accessToken);
            }
            return client;
        }

        private static async Task<GameAssetDbConfig> LoadConfigAsync()
        {
            var configDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "GameAssetDB");
            var configPath = Path.Combine(configDirectory, ConfigFileName);

            if (!File.Exists(configPath))
            {
                Directory.CreateDirectory(configDirectory);
                var defaultConfig = JsonSerializer.Serialize(new GameAssetDbConfig(), WriteJsonOptions);
                await File.WriteAllTextAsync(configPath, defaultConfig, Encoding.UTF8);
            }

            var json = await File.ReadAllTextAsync(configPath, Encoding.UTF8);
            var config = JsonSerializer.Deserialize<GameAssetDbConfig>(json, ReadJsonOptions);
            return config ?? new GameAssetDbConfig();
        }

        private static bool TryGetMetadataString(JsonElement metadata, string propertyName, out string value)
        {
            value = string.Empty;
            if (metadata.ValueKind != JsonValueKind.Object)
            {
                return false;
            }

            if (!metadata.TryGetProperty(propertyName, out var element))
            {
                return false;
            }

            if (element.ValueKind == JsonValueKind.String)
            {
                value = element.GetString();
                return true;
            }

            if (element.ValueKind == JsonValueKind.Number && element.TryGetDouble(out var number))
            {
                value = number.ToString();
                return true;
            }

            return false;
        }

        private static string SanitizeFolderName(string name)
        {
            foreach (var invalidChar in Path.GetInvalidFileNameChars())
            {
                name = name.Replace(invalidChar, '_');
            }

            return name;
        }

        private class GameAssetDbConfig
        {
            public string ApiBaseUrl { get; set; } = "https://game-asset-db.example.com/api";
            public string ProjectId { get; set; } = string.Empty;
            public string Username { get; set; } = "artist";
            public string Password { get; set; } = "changeme";
        }

        private class TokenRequest
        {
            [JsonPropertyName("username")]
            public string Username { get; set; }

            [JsonPropertyName("password")]
            public string Password { get; set; }
        }

        private class TokenResponse
        {
            [JsonPropertyName("access_token")]
            public string AccessToken { get; set; }

            [JsonPropertyName("expires_in")]
            public int ExpiresIn { get; set; } = 3600;
        }

        private class AssetSummary
        {
            public Guid Id { get; set; }
            public string Name { get; set; }
            public string Type { get; set; }
            public Guid ProjectId { get; set; }
            public JsonElement Metadata { get; set; }
            public List<AssetVersion> Versions { get; set; } = new();

            [JsonIgnore]
            public string LatestVersion => Versions != null && Versions.Count > 0 ? Versions[Versions.Count - 1].VersionNumber.ToString() : "0";
        }

        private class AssetDetail : AssetSummary
        {
        }

        private class AssetVersion
        {
            public Guid Id { get; set; }

            [JsonPropertyName("version_number")]
            public int VersionNumber { get; set; }

            [JsonPropertyName("branch_id")]
            public Guid? BranchId { get; set; }

            [JsonPropertyName("file_path")]
            public string FilePath { get; set; }

            public string Notes { get; set; }

            [JsonPropertyName("created_at")]
            public DateTime CreatedAt { get; set; }
        }
    }
}
