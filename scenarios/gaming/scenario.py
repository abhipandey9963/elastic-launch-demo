"""Live Gaming Platform scenario — multiplayer gaming infrastructure with live-ops chaos engineering."""

from __future__ import annotations

import random
import time
from typing import Any

from scenarios.base import BaseScenario, CountdownConfig, UITheme


class GamingScenario(BaseScenario):
    """Live multiplayer gaming platform with 9 game services and 20 fault channels."""

    # ── Identity ──────────────────────────────────────────────────────

    @property
    def scenario_id(self) -> str:
        return "gaming"

    @property
    def scenario_name(self) -> str:
        return "Live Gaming Platform"

    @property
    def scenario_description(self) -> str:
        return (
            "Live multiplayer gaming platform with game servers, matchmaking, "
            "content delivery, chat, leaderboards, authentication, payments, "
            "analytics, and content moderation. Cyberpunk neon command center."
        )

    @property
    def namespace(self) -> str:
        return "gaming"

    # ── Services ──────────────────────────────────────────────────────

    @property
    def services(self) -> dict[str, dict[str, Any]]:
        return {
            "game-server": {
                "cloud_provider": "aws",
                "cloud_region": "us-east-1",
                "cloud_platform": "aws_ec2",
                "cloud_availability_zone": "us-east-1a",
                "subsystem": "game_engine",
                "language": "cpp",
            },
            "matchmaking-engine": {
                "cloud_provider": "aws",
                "cloud_region": "us-east-1",
                "cloud_platform": "aws_ec2",
                "cloud_availability_zone": "us-east-1b",
                "subsystem": "matchmaking",
                "language": "go",
            },
            "content-delivery": {
                "cloud_provider": "aws",
                "cloud_region": "us-east-1",
                "cloud_platform": "aws_ec2",
                "cloud_availability_zone": "us-east-1c",
                "subsystem": "cdn",
                "language": "rust",
            },
            "chat-service": {
                "cloud_provider": "gcp",
                "cloud_region": "us-central1",
                "cloud_platform": "gcp_compute_engine",
                "cloud_availability_zone": "us-central1-a",
                "subsystem": "social",
                "language": "java",
            },
            "leaderboard-api": {
                "cloud_provider": "gcp",
                "cloud_region": "us-central1",
                "cloud_platform": "gcp_compute_engine",
                "cloud_availability_zone": "us-central1-b",
                "subsystem": "progression",
                "language": "go",
            },
            "auth-gateway": {
                "cloud_provider": "gcp",
                "cloud_region": "us-central1",
                "cloud_platform": "gcp_compute_engine",
                "cloud_availability_zone": "us-central1-a",
                "subsystem": "identity",
                "language": "python",
            },
            "payment-processor": {
                "cloud_provider": "azure",
                "cloud_region": "eastus",
                "cloud_platform": "azure_vm",
                "cloud_availability_zone": "eastus-1",
                "subsystem": "monetization",
                "language": "dotnet",
            },
            "analytics-pipeline": {
                "cloud_provider": "azure",
                "cloud_region": "eastus",
                "cloud_platform": "azure_vm",
                "cloud_availability_zone": "eastus-2",
                "subsystem": "analytics",
                "language": "python",
            },
            "moderation-engine": {
                "cloud_provider": "azure",
                "cloud_region": "eastus",
                "cloud_platform": "azure_vm",
                "cloud_availability_zone": "eastus-1",
                "subsystem": "trust_safety",
                "language": "java",
            },
        }

    # ── Channel Registry ──────────────────────────────────────────────

    @property
    def channel_registry(self) -> dict[int, dict[str, Any]]:
        return {
            1: {
                "name": "Game State Desync",
                "subsystem": "game_engine",
                "vehicle_section": "game_loop",
                "error_type": "NET-STATE-DESYNC",
                "sensor_type": "state_validator",
                "affected_services": ["game-server", "matchmaking-engine"],
                "cascade_services": ["analytics-pipeline"],
                "description": "Game state diverges between server authoritative state and client prediction, causing rubber-banding and rollback cascades",
                "error_message": "[Net] NET-STATE-DESYNC: player={player_id} pos_delta={position_delta}m threshold=0.5m tick={tick_number} match={match_id}",
                "stack_trace": (
                    "=== NET STATE RECONCILIATION DUMP ===\n"
                    "match={match_id}  tick={tick_number}  player={player_id}\n"
                    "----------- server state -----------\n"
                    "  pos  = (1247.32, 45.00, -892.17)\n"
                    "  vel  = (3.41, 0.00, -1.22)\n"
                    "  yaw  = 127.4 deg\n"
                    "  seq  = 48201\n"
                    "----------- client state -----------\n"
                    "  pos  = (1248.87, 45.00, -893.40)  delta={position_delta}m\n"
                    "  vel  = (4.02, 0.00, -1.87)\n"
                    "  yaw  = 128.1 deg\n"
                    "  seq  = 48199  (2 behind)\n"
                    "----------- action -----------------\n"
                    "  FORCE_RECONCILE  rollback_ticks=3  bandwidth_cost=2.4KB\n"
                    "  client_rtt=47ms  jitter=8ms  interp_delay=100ms\n"
                    "NET-STATE-DESYNC: threshold exceeded — forced reconcile for player {player_id}"
                ),
            },
            2: {
                "name": "Physics Simulation Overflow",
                "subsystem": "game_engine",
                "vehicle_section": "physics_engine",
                "error_type": "PHYS-OVERFLOW",
                "sensor_type": "physics_validator",
                "affected_services": ["game-server", "analytics-pipeline"],
                "cascade_services": ["matchmaking-engine"],
                "description": "Physics simulation accumulates floating-point errors causing object positions to overflow into NaN territory",
                "error_message": "[Physics] PHYS-OVERFLOW: entity={entity_id} velocity={velocity} max={max_velocity} zone={zone_id} tick={tick_number}",
                "stack_trace": (
                    "=== PHYSICS ENGINE STATE DUMP ===\n"
                    "tick={tick_number}  zone={zone_id}  substep=4/4\n"
                    "----------- entity {entity_id} -----------\n"
                    "  pos       = (8421.7, 102.3, -3304.9)\n"
                    "  vel       = ({velocity}, 0.0, 0.0)  |v|={velocity}\n"
                    "  max_vel   = {max_velocity}\n"
                    "  accel     = (12842.1, 0.0, -4201.3)\n"
                    "  mass      = 85.0 kg\n"
                    "  collider  = CAPSULE r=0.4 h=1.8\n"
                    "----------- collision candidates --------\n"
                    "  broadphase_pairs = 47\n"
                    "  narrowphase_hits = 3\n"
                    "  penetration_max  = 0.82m (ENT-29481 <-> ENT-30012)\n"
                    "----------- action ----------------------\n"
                    "  CLAMP velocity to {max_velocity}  REWIND substep 3\n"
                    "PHYS-OVERFLOW: entity {entity_id} velocity {velocity} exceeds simulation limit {max_velocity}"
                ),
            },
            3: {
                "name": "Matchmaking Queue Overflow",
                "subsystem": "matchmaking",
                "vehicle_section": "matchmaker_core",
                "error_type": "MM-QUEUE-OVERFLOW",
                "sensor_type": "queue_monitor",
                "affected_services": ["matchmaking-engine", "game-server"],
                "cascade_services": ["auth-gateway", "analytics-pipeline"],
                "description": "Matchmaking queue depth exceeds capacity causing player wait times to spike beyond acceptable thresholds",
                "error_message": "[MM] MM-QUEUE-OVERFLOW: pool={queue_name} queue={queue_depth} max={max_capacity} wait_p99={wait_time_ms}ms region={region}",
                "stack_trace": (
                    "=== MATCHMAKING QUEUE STATE DUMP ===\n"
                    "pool={queue_name}  region={region}\n"
                    "----------- queue metrics -----------\n"
                    "  depth       = {queue_depth}  (max {max_capacity})\n"
                    "  wait_p50    = 12400ms\n"
                    "  wait_p95    = 87200ms\n"
                    "  wait_p99    = {wait_time_ms}ms\n"
                    "  enqueue/s   = 342\n"
                    "  dequeue/s   = 89\n"
                    "  drain_eta   = NEVER (inflow > outflow)\n"
                    "----------- pool breakdown ----------\n"
                    "  bronze-silver  : 4201 waiting\n"
                    "  gold-platinum  : 2847 waiting\n"
                    "  diamond+       : 891 waiting\n"
                    "----------- action ------------------\n"
                    "  EXPAND mmr_range +200  RELAX region_lock\n"
                    "MM-QUEUE-OVERFLOW: pool {queue_name} saturated at {queue_depth}/{max_capacity}"
                ),
            },
            4: {
                "name": "Skill Rating Calculation Error",
                "subsystem": "matchmaking",
                "vehicle_section": "rating_engine",
                "error_type": "MM-SKILL-RATING-DIVERGE",
                "sensor_type": "rating_validator",
                "affected_services": ["matchmaking-engine", "leaderboard-api"],
                "cascade_services": ["analytics-pipeline"],
                "description": "Skill rating calculation produces invalid MMR values due to edge cases in the Elo/Glicko algorithm implementation",
                "error_message": "[MM] MM-SKILL-RATING-DIVERGE: player={player_id} mmr={mmr_value} valid_range=[0,{max_mmr}] volatility={volatility} match={match_id}",
                "stack_trace": (
                    "=== GLICKO-2 CALCULATION TRACE ===\n"
                    "player={player_id}  match={match_id}\n"
                    "----------- pre-match state ----------\n"
                    "  mu (rating)     = 1847.3\n"
                    "  phi (deviation) = 142.7\n"
                    "  sigma (vol)     = {volatility}\n"
                    "  games_in_period = 14\n"
                    "----------- match result -------------\n"
                    "  opponents       = 5\n"
                    "  actual_score    = 0.83\n"
                    "  expected_score  = 0.41\n"
                    "  k_factor        = 32.0\n"
                    "----------- post-match calc ----------\n"
                    "  new_mu          = {mmr_value}  <<< OUT OF RANGE [0, {max_mmr}]\n"
                    "  new_phi         = 187.2\n"
                    "  new_sigma       = 0.089\n"
                    "  convergence_i   = 12 iterations (max 20)\n"
                    "----------- action -------------------\n"
                    "  CLAMP to valid range  FLAG for manual review\n"
                    "MM-SKILL-RATING-DIVERGE: player {player_id} mmr {mmr_value} outside bounds"
                ),
            },
            5: {
                "name": "CDN Cache Miss Storm",
                "subsystem": "cdn",
                "vehicle_section": "cdn_edge",
                "error_type": "CDN-CACHE-MISS-STORM",
                "sensor_type": "cache_monitor",
                "affected_services": ["content-delivery", "game-server"],
                "cascade_services": ["analytics-pipeline"],
                "description": "Cascading cache misses overwhelm origin servers as hot content expires simultaneously across edge nodes",
                "error_message": "[CDN] CDN-CACHE-MISS-STORM: edge={edge_node} hit_rate={cache_hit_rate}% threshold=85% origin_load={origin_load_pct}% asset_group={asset_group}",
                "stack_trace": (
                    "=== CDN EDGE NODE CACHE STATISTICS ===\n"
                    "edge={edge_node}  asset_group={asset_group}\n"
                    "----------- cache metrics -----------\n"
                    "  hit_rate    = {cache_hit_rate}%  (threshold 85%)\n"
                    "  miss_rate   = {origin_load_pct}%\n"
                    "  evictions   = 14,203/min\n"
                    "  warm_pct    = 32.1%\n"
                    "  cold_pct    = 67.9%\n"
                    "----------- origin load -------------\n"
                    "  rps_to_origin   = 8,421\n"
                    "  origin_p99_ms   = 847\n"
                    "  origin_errors   = 127 (circuit_breaker=HALF_OPEN)\n"
                    "  bandwidth_gbps  = 12.4\n"
                    "----------- top miss groups ---------\n"
                    "  textures-hd     : 4,201 misses/min\n"
                    "  models-char     : 2,103 misses/min\n"
                    "  audio-sfx       : 891 misses/min\n"
                    "CDN-CACHE-MISS-STORM: edge {edge_node} hit rate {cache_hit_rate}% below threshold"
                ),
            },
            6: {
                "name": "Asset Bundle Corruption",
                "subsystem": "cdn",
                "vehicle_section": "asset_pipeline",
                "error_type": "CDN-ASSET-CORRUPT",
                "sensor_type": "integrity_checker",
                "affected_services": ["content-delivery", "game-server"],
                "cascade_services": ["moderation-engine"],
                "description": "Game asset bundles fail integrity verification after CDN transfer, causing client crashes on load",
                "error_message": "[CDN] CDN-ASSET-CORRUPT: bundle={bundle_id} expected={expected_hash} actual={actual_hash} size={bundle_size_mb}MB version={bundle_version}",
                "stack_trace": (
                    "=== ASSET INTEGRITY VERIFICATION LOG ===\n"
                    "bundle={bundle_id}  version={bundle_version}\n"
                    "----------- checksums ---------------\n"
                    "  expected  = {expected_hash}\n"
                    "  actual    = {actual_hash}\n"
                    "  algorithm = SHA-256\n"
                    "----------- bundle info -------------\n"
                    "  size        = {bundle_size_mb}MB\n"
                    "  chunks      = 48\n"
                    "  chunk_size  = 4MB\n"
                    "  corrupt_chunk = 23 (offset 92274688)\n"
                    "  edge_source   = edge-iad-01\n"
                    "----------- transfer log ------------\n"
                    "  started    = 2026-02-17T14:22:01.847Z\n"
                    "  completed  = 2026-02-17T14:22:04.213Z\n"
                    "  retries    = 1\n"
                    "  tcp_resets = 2\n"
                    "CDN-ASSET-CORRUPT: bundle {bundle_id} checksum mismatch — quarantined"
                ),
            },
            7: {
                "name": "Chat Message Flood",
                "subsystem": "social",
                "vehicle_section": "chat_gateway",
                "error_type": "CHAT-FLOOD-DETECT",
                "sensor_type": "rate_limiter",
                "affected_services": ["chat-service", "moderation-engine"],
                "cascade_services": ["auth-gateway"],
                "description": "Chat channels experiencing message floods that overwhelm rate limiters and moderation pipelines",
                "error_message": "[Chat] CHAT-FLOOD-DETECT: channel={channel_id} rate={message_rate}msg/s threshold={rate_limit}msg/s pending_mod={pending_moderation}",
                "stack_trace": (
                    "=== CHAT RATE LIMITER STATE DUMP ===\n"
                    "channel={channel_id}\n"
                    "----------- rate metrics ------------\n"
                    "  current_rate   = {message_rate} msg/s\n"
                    "  threshold      = {rate_limit} msg/s\n"
                    "  burst_window   = 5s\n"
                    "  burst_peak     = {message_rate} msg/s\n"
                    "----------- moderation queue --------\n"
                    "  pending        = {pending_moderation}\n"
                    "  avg_scan_ms    = 12.4\n"
                    "  automod_queue  = 87% full\n"
                    "  dropped_scans  = 421\n"
                    "----------- top senders -------------\n"
                    "  PLR-482910  : 47 msg/s (BOT_SUSPECT)\n"
                    "  PLR-109284  : 31 msg/s (BOT_SUSPECT)\n"
                    "  PLR-773201  : 28 msg/s (NORMAL)\n"
                    "----------- action ------------------\n"
                    "  THROTTLE channel to {rate_limit} msg/s  QUEUE moderation backlog\n"
                    "CHAT-FLOOD-DETECT: channel {channel_id} rate {message_rate}msg/s exceeds threshold"
                ),
            },
            8: {
                "name": "Voice Channel Degradation",
                "subsystem": "social",
                "vehicle_section": "voice_server",
                "error_type": "VOICE-CHANNEL-OVERLOAD",
                "sensor_type": "audio_quality_monitor",
                "affected_services": ["chat-service", "game-server"],
                "cascade_services": ["analytics-pipeline"],
                "description": "Voice chat channels experiencing audio quality degradation with packet loss, jitter, and codec failures",
                "error_message": "[Voice] VOICE-CHANNEL-OVERLOAD: channel={voice_channel_id} loss={voice_packet_loss_pct}% jitter={jitter_ms}ms speakers={active_speakers} codec={codec}",
                "stack_trace": (
                    "=== VOICE SERVER QUALITY METRICS ===\n"
                    "channel={voice_channel_id}  codec={codec}\n"
                    "----------- per-stream stats --------\n"
                    "  stream_count     = {active_speakers}\n"
                    "  packet_loss_avg  = {voice_packet_loss_pct}%\n"
                    "  jitter_avg       = {jitter_ms}ms\n"
                    "  jitter_max       = 287ms\n"
                    "  bitrate          = 64kbps (target 96kbps — downgraded)\n"
                    "  fec_recovery     = 12.3%\n"
                    "----------- worst streams -----------\n"
                    "  PLR-481020  loss=34.2%  jitter=198ms  MOS=1.8\n"
                    "  PLR-229103  loss=28.7%  jitter=154ms  MOS=2.1\n"
                    "  PLR-884712  loss=19.1%  jitter=112ms  MOS=2.6\n"
                    "----------- server state ------------\n"
                    "  cpu_pct     = 87.4%\n"
                    "  mix_latency = 23ms (target 10ms)\n"
                    "  udp_rx_drop = 4.2%\n"
                    "VOICE-CHANNEL-OVERLOAD: channel {voice_channel_id} quality degraded — {voice_packet_loss_pct}% loss"
                ),
            },
            9: {
                "name": "Leaderboard Corruption",
                "subsystem": "progression",
                "vehicle_section": "leaderboard_core",
                "error_type": "LB-DATA-CORRUPT",
                "sensor_type": "consistency_checker",
                "affected_services": ["leaderboard-api", "game-server"],
                "cascade_services": ["analytics-pipeline", "moderation-engine"],
                "description": "Leaderboard sorted set becomes inconsistent due to concurrent score updates causing rank calculation errors",
                "error_message": "[LB] LB-DATA-CORRUPT: board={leaderboard_id} affected={corrupt_entries} checksum_fail=true season={season_id}",
                "stack_trace": (
                    "=== LEADERBOARD CONSISTENCY CHECK ===\n"
                    "board={leaderboard_id}  season={season_id}\n"
                    "----------- sorted set audit --------\n"
                    "  total_entries    = 1,284,301\n"
                    "  corrupt_entries  = {corrupt_entries}\n"
                    "  checksum_fail    = true\n"
                    "  last_valid_rank  = 42,017\n"
                    "----------- sample violations -------\n"
                    "  rank 42018: score=8401 > rank 42017: score=8399  (INVERSION)\n"
                    "  rank 42019: score=8401  (DUPLICATE score, different player)\n"
                    "  rank 42103: score=NaN   (CORRUPT value)\n"
                    "----------- redis state -------------\n"
                    "  zset_card    = 1,284,301\n"
                    "  memory_used  = 142MB\n"
                    "  last_write   = 2026-02-17T14:21:58.441Z\n"
                    "  aof_rewrite  = IN_PROGRESS\n"
                    "----------- action ------------------\n"
                    "  FREEZE board  REBUILD from transaction log\n"
                    "LB-DATA-CORRUPT: board {leaderboard_id} has {corrupt_entries} invalid entries"
                ),
            },
            10: {
                "name": "Season Pass Progression Sync Error",
                "subsystem": "progression",
                "vehicle_section": "progression_tracker",
                "error_type": "SEASON-PASS-SYNC-FAIL",
                "sensor_type": "sync_validator",
                "affected_services": ["leaderboard-api", "payment-processor"],
                "cascade_services": ["analytics-pipeline"],
                "description": "Season pass XP and tier progression fails to synchronize between game server events and the progression backend",
                "error_message": "[LB] SEASON-PASS-SYNC-FAIL: player={player_id} tier={current_tier} expected_tier={expected_tier} xp={xp_total} delta={xp_delta}XP season={season_id}",
                "stack_trace": (
                    "=== SEASON PASS PROGRESSION STATE ===\n"
                    "player={player_id}  season={season_id}\n"
                    "----------- current state -----------\n"
                    "  tier         = {current_tier}\n"
                    "  xp_total     = {xp_total}\n"
                    "  xp_to_next   = 2,500\n"
                    "  premium      = true\n"
                    "----------- expected state ----------\n"
                    "  expected_tier = {expected_tier}\n"
                    "  xp_delta      = {xp_delta}XP (unaccounted)\n"
                    "  tier_threshold = {xp_total} XP -> tier {expected_tier}\n"
                    "----------- recent xp events --------\n"
                    "  match_complete  +1,200 XP  (2min ago)\n"
                    "  daily_challenge +800 XP    (4min ago)\n"
                    "  kill_streak     +350 XP    (5min ago)  <-- NOT APPLIED\n"
                    "  weekly_bonus    +2,000 XP  (12min ago) <-- NOT APPLIED\n"
                    "----------- action ------------------\n"
                    "  FORCE_SYNC tier to {expected_tier}  REPLAY missed events\n"
                    "SEASON-PASS-SYNC-FAIL: player {player_id} stuck at tier {current_tier}, should be {expected_tier}"
                ),
            },
            11: {
                "name": "OAuth Token Refresh Storm",
                "subsystem": "identity",
                "vehicle_section": "auth_core",
                "error_type": "AUTH-TOKEN-STORM",
                "sensor_type": "token_monitor",
                "affected_services": ["auth-gateway", "game-server"],
                "cascade_services": ["matchmaking-engine", "chat-service"],
                "description": "Mass token refresh requests overwhelm the auth service when tokens expire simultaneously due to clock sync issues",
                "error_message": "[Auth] AUTH-TOKEN-STORM: refresh_rate={refresh_rate}/s capacity={max_refresh_rate}/s failures={failed_refreshes} pool={token_pool_id}",
                "stack_trace": (
                    "=== TOKEN SERVICE METRICS DUMP ===\n"
                    "pool={token_pool_id}\n"
                    "----------- refresh metrics ---------\n"
                    "  refresh_rate    = {refresh_rate}/s\n"
                    "  capacity        = {max_refresh_rate}/s\n"
                    "  failures        = {failed_refreshes}\n"
                    "  success_rate    = 14.2%\n"
                    "  avg_latency     = 4,821ms (target 50ms)\n"
                    "----------- token pool state --------\n"
                    "  active_tokens   = 142,301\n"
                    "  expiring_5min   = 87,412  (61.4% — clock skew)\n"
                    "  signing_key     = RS256-prod-2026-02\n"
                    "  jwks_cache_age  = 312s\n"
                    "----------- provider breakdown ------\n"
                    "  oauth-google    : 3,201/s (OVERLOADED)\n"
                    "  oauth-discord   : 2,847/s (OVERLOADED)\n"
                    "  oauth-steam     : 1,204/s (DEGRADED)\n"
                    "  email-password  : 891/s   (OK)\n"
                    "----------- action ------------------\n"
                    "  STAGGER refresh window  EXTEND ttl by 300s\n"
                    "AUTH-TOKEN-STORM: refresh rate {refresh_rate}/s exceeds capacity {max_refresh_rate}/s"
                ),
            },
            12: {
                "name": "Account Takeover Detection Spike",
                "subsystem": "identity",
                "vehicle_section": "fraud_detector",
                "error_type": "AUTH-TAKEOVER-DETECT",
                "sensor_type": "anomaly_detector",
                "affected_services": ["auth-gateway", "payment-processor"],
                "cascade_services": ["moderation-engine", "analytics-pipeline"],
                "description": "Anomaly detection system flags a surge in credential stuffing attempts indicating a coordinated account takeover campaign",
                "error_message": "[Auth] AUTH-TAKEOVER-DETECT: attempts={ato_attempts} window={window_seconds}s blocked_ips={blocked_ips} risk={risk_score} geo={geo_region}",
                "stack_trace": (
                    "=== ATO DETECTION ANALYSIS ===\n"
                    "window={window_seconds}s  geo={geo_region}\n"
                    "----------- attempt metrics ---------\n"
                    "  total_attempts  = {ato_attempts}\n"
                    "  unique_ips      = {blocked_ips}\n"
                    "  credential_pairs = 12,401\n"
                    "  success_rate    = 0.3% (credential stuffing pattern)\n"
                    "  risk_score      = {risk_score}\n"
                    "----------- geo analysis ------------\n"
                    "  primary_region  = {geo_region}\n"
                    "  ip_reputation   = 87% known-bad\n"
                    "  vpn_pct         = 94.2%\n"
                    "  tor_exit_nodes  = 12\n"
                    "----------- attack pattern ----------\n"
                    "  type            = CREDENTIAL_STUFFING\n"
                    "  rate            = {ato_attempts} / {window_seconds}s\n"
                    "  user_agent_entropy = LOW (bot signature)\n"
                    "  request_interval   = 0.8ms avg (automated)\n"
                    "----------- action ------------------\n"
                    "  BLOCK {blocked_ips} IPs  ENABLE captcha  NOTIFY security team\n"
                    "AUTH-TAKEOVER-DETECT: {ato_attempts} attempts from {blocked_ips} IPs, risk {risk_score}"
                ),
            },
            13: {
                "name": "In-App Purchase Processing Failure",
                "subsystem": "monetization",
                "vehicle_section": "payment_gateway",
                "error_type": "IAP-PURCHASE-FAIL",
                "sensor_type": "transaction_monitor",
                "affected_services": ["payment-processor", "auth-gateway"],
                "cascade_services": ["analytics-pipeline"],
                "description": "In-app purchase transactions failing at the payment gateway level due to provider timeouts or validation errors",
                "error_message": "[IAP] IAP-PURCHASE-FAIL: txn={purchase_id} player={player_id} amount={amount}{currency} provider={payment_provider} code={error_code} retry={retry_count}/{max_retries}",
                "stack_trace": (
                    "=== PAYMENT GATEWAY TRANSACTION TRACE ===\n"
                    "txn={purchase_id}  player={player_id}\n"
                    "----------- request -----------------\n"
                    "  amount       = {amount} {currency}\n"
                    "  provider     = {payment_provider}\n"
                    "  item_sku     = SKU-PREMIUM-PACK-01\n"
                    "  idempotency  = {purchase_id}-r{retry_count}\n"
                    "----------- provider response -------\n"
                    "  status_code  = 402\n"
                    "  error_code   = {error_code}\n"
                    "  latency_ms   = 8,412\n"
                    "  gateway_txn  = GW-8a4f2e1b-c930\n"
                    "----------- retry state -------------\n"
                    "  attempt      = {retry_count}/{max_retries}\n"
                    "  backoff_ms   = 4,000\n"
                    "  next_retry   = 2026-02-17T14:22:08.000Z\n"
                    "----------- receipt validation ------\n"
                    "  receipt_valid = false\n"
                    "  signature    = (not provided — payment not completed)\n"
                    "IAP-PURCHASE-FAIL: txn {purchase_id} failed with {error_code} via {payment_provider}"
                ),
            },
            14: {
                "name": "Virtual Currency Ledger Inconsistency",
                "subsystem": "monetization",
                "vehicle_section": "ledger_service",
                "error_type": "IAP-LEDGER-INCONSIST",
                "sensor_type": "ledger_auditor",
                "affected_services": ["payment-processor", "leaderboard-api"],
                "cascade_services": ["moderation-engine", "analytics-pipeline"],
                "description": "Virtual currency ledger double-entry balances fail reconciliation, indicating potential duplication or lost transactions",
                "error_message": "[IAP] IAP-LEDGER-INCONSIST: player={player_id} balance={currency_balance} ledger_sum={ledger_sum} currency={virtual_currency} discrepancy={discrepancy} last_txn={last_transaction_id}",
                "stack_trace": (
                    "=== LEDGER RECONCILIATION REPORT ===\n"
                    "player={player_id}  currency={virtual_currency}\n"
                    "----------- balance check -----------\n"
                    "  cached_balance  = {currency_balance}\n"
                    "  ledger_sum      = {ledger_sum}\n"
                    "  discrepancy     = {discrepancy}\n"
                    "  tolerance       = 1\n"
                    "----------- recent transactions -----\n"
                    "  {last_transaction_id}  +500 {virtual_currency}  (purchase, 2min ago)\n"
                    "  LTXN-8847201          -200 {virtual_currency}  (spend, 4min ago)\n"
                    "  LTXN-8847102          +100 {virtual_currency}  (daily reward, 8min ago)\n"
                    "  LTXN-8846990          -50 {virtual_currency}   (spend, 12min ago)\n"
                    "----------- audit flags -------------\n"
                    "  duplicate_txn   = POSSIBLE ({last_transaction_id} applied twice?)\n"
                    "  race_condition  = LIKELY (concurrent write detected)\n"
                    "  fraud_risk      = LOW\n"
                    "----------- action ------------------\n"
                    "  FREEZE player wallet  RECONCILE from ledger source of truth\n"
                    "IAP-LEDGER-INCONSIST: player {player_id} balance {currency_balance} != ledger {ledger_sum}"
                ),
            },
            15: {
                "name": "Event Ingestion Pipeline Lag",
                "subsystem": "analytics",
                "vehicle_section": "ingestion_pipeline",
                "error_type": "ANALYTICS-INGEST-LAG",
                "sensor_type": "pipeline_monitor",
                "affected_services": ["analytics-pipeline", "game-server"],
                "cascade_services": ["leaderboard-api"],
                "description": "Analytics event ingestion pipeline falls behind, causing data lag and stale dashboards for live-ops teams",
                "error_message": "[Analytics] ANALYTICS-INGEST-LAG: pipeline={pipeline_id} lag={lag_seconds}s threshold={max_lag_seconds}s backlog={backlog_count} throughput={throughput}/s",
                "stack_trace": (
                    "=== PIPELINE CONSUMER GROUP STATUS ===\n"
                    "pipeline={pipeline_id}\n"
                    "----------- consumer lag ------------\n"
                    "  current_lag     = {lag_seconds}s\n"
                    "  threshold       = {max_lag_seconds}s\n"
                    "  backlog         = {backlog_count} events\n"
                    "  throughput      = {throughput}/s (expected {expected_throughput}/s)\n"
                    "----------- partition status --------\n"
                    "  partition-0  offset=48201847  lag=12,401\n"
                    "  partition-1  offset=48193201  lag=21,047\n"
                    "  partition-2  offset=48198412  lag=15,882\n"
                    "  partition-3  offset=48187003  lag=27,193  (STALLED)\n"
                    "----------- consumer group ----------\n"
                    "  group_id     = {pipeline_id}-cg\n"
                    "  members      = 4/8 (4 DISCONNECTED)\n"
                    "  rebalance_ct = 3 (last 10min)\n"
                    "  commit_lag   = 8.2s\n"
                    "----------- action ------------------\n"
                    "  RESTART stalled consumers  SCALE OUT partitions\n"
                    "ANALYTICS-INGEST-LAG: pipeline {pipeline_id} lag {lag_seconds}s with {backlog_count} backlog"
                ),
            },
            16: {
                "name": "Player Telemetry Buffer Overflow",
                "subsystem": "analytics",
                "vehicle_section": "telemetry_buffer",
                "error_type": "ANALYTICS-TELEMETRY-OVERFLOW",
                "sensor_type": "buffer_monitor",
                "affected_services": ["analytics-pipeline", "game-server"],
                "cascade_services": ["matchmaking-engine"],
                "description": "Player telemetry ring buffer overflows causing event data loss for analytics and anti-cheat systems",
                "error_message": "[Analytics] ANALYTICS-TELEMETRY-OVERFLOW: buffer={buffer_id} usage={buffer_usage_pct}% capacity={buffer_size}/{max_buffer_size} dropped={dropped_events}",
                "stack_trace": (
                    "=== RING BUFFER DIAGNOSTIC ===\n"
                    "buffer={buffer_id}\n"
                    "----------- buffer state ------------\n"
                    "  usage        = {buffer_usage_pct}%\n"
                    "  size         = {buffer_size}/{max_buffer_size}\n"
                    "  head_offset  = 99,847\n"
                    "  tail_offset  = 99,201\n"
                    "  writable     = 646 slots\n"
                    "----------- drop statistics ---------\n"
                    "  dropped_total   = {dropped_events}\n"
                    "  dropped_1min    = 1,204\n"
                    "  dropped_5min    = 4,821\n"
                    "  drop_rate       = 12.4%\n"
                    "----------- event breakdown ---------\n"
                    "  player_move     : 42.1% of buffer\n"
                    "  combat_event    : 28.4% of buffer\n"
                    "  state_snapshot  : 18.7% of buffer\n"
                    "  misc            : 10.8% of buffer\n"
                    "----------- action ------------------\n"
                    "  EVICT oldest 20%  ALERT anti-cheat (data gap)\n"
                    "ANALYTICS-TELEMETRY-OVERFLOW: buffer {buffer_id} at {buffer_usage_pct}% — {dropped_events} events lost"
                ),
            },
            17: {
                "name": "Auto-Moderation False Positive Storm",
                "subsystem": "trust_safety",
                "vehicle_section": "automod_engine",
                "error_type": "MOD-FALSE-POS-STORM",
                "sensor_type": "accuracy_monitor",
                "affected_services": ["moderation-engine", "chat-service"],
                "cascade_services": ["analytics-pipeline"],
                "description": "Automated content moderation system producing excessive false positives, silencing legitimate player communication",
                "error_message": "[T&S] MOD-FALSE-POS-STORM: flagged={false_positive_count} window={window_minutes}min fp_rate={fp_rate_pct}% model={model_version} affected_players={affected_players}",
                "stack_trace": (
                    "=== AUTOMOD ACCURACY METRICS ===\n"
                    "model={model_version}  window={window_minutes}min\n"
                    "----------- classification stats ----\n"
                    "  total_scanned    = 84,201\n"
                    "  true_positives   = 412\n"
                    "  false_positives  = {false_positive_count}\n"
                    "  false_negatives  = 23\n"
                    "  fp_rate          = {fp_rate_pct}%\n"
                    "  precision        = 0.42\n"
                    "  recall           = 0.95\n"
                    "----------- category breakdown ------\n"
                    "  harassment   : fp_rate=12.1%  (normal: 1.2%)\n"
                    "  hate_speech  : fp_rate=34.8%  (normal: 2.1%)  <<< SPIKE\n"
                    "  spam         : fp_rate=8.4%   (normal: 3.1%)\n"
                    "  exploits     : fp_rate=2.1%   (normal: 0.8%)\n"
                    "----------- affected players --------\n"
                    "  silenced    = {affected_players}\n"
                    "  appeals     = 847 (pending)\n"
                    "  overturned  = 0 (queue backed up)\n"
                    "----------- action ------------------\n"
                    "  ROLLBACK to {model_version}-prev  UNSILENCE affected players\n"
                    "MOD-FALSE-POS-STORM: {false_positive_count} false positives at {fp_rate_pct}% rate"
                ),
            },
            18: {
                "name": "Report Queue Overflow",
                "subsystem": "trust_safety",
                "vehicle_section": "report_processor",
                "error_type": "MOD-REPORT-QUEUE-OVERFLOW",
                "sensor_type": "queue_monitor",
                "affected_services": ["moderation-engine", "chat-service"],
                "cascade_services": ["auth-gateway"],
                "description": "Player report queue exceeds processing capacity causing delays in abuse case resolution",
                "error_message": "[T&S] MOD-REPORT-QUEUE-OVERFLOW: queue={report_queue_depth} rate={processing_rate}/min oldest={oldest_report_hours}h category={report_category}",
                "stack_trace": (
                    "=== REPORT QUEUE STATUS ===\n"
                    "category={report_category}\n"
                    "----------- queue metrics -----------\n"
                    "  depth           = {report_queue_depth}\n"
                    "  processing_rate = {processing_rate}/min\n"
                    "  oldest_report   = {oldest_report_hours}h\n"
                    "  drain_eta       = NEVER (inflow > capacity)\n"
                    "----------- category breakdown ------\n"
                    "  harassment   : 8,421 pending  (SLA: 4h, actual: 12h)\n"
                    "  cheating     : 4,201 pending  (SLA: 2h, actual: 8h)\n"
                    "  hate_speech  : 2,847 pending  (SLA: 1h, actual: 6h)\n"
                    "  exploits     : 1,204 pending  (SLA: 4h, actual: 24h)\n"
                    "  spam         : 891 pending    (SLA: 8h, actual: 48h)\n"
                    "----------- processor state ---------\n"
                    "  workers_active  = 4/12 (8 CRASHED)\n"
                    "  gpu_inference   = DEGRADED (OOM on 2 nodes)\n"
                    "  auto_resolve    = DISABLED (fp_rate too high)\n"
                    "----------- action ------------------\n"
                    "  RESTART crashed workers  PRIORITIZE by SLA breach\n"
                    "MOD-REPORT-QUEUE-OVERFLOW: queue {report_queue_depth} reports, oldest {oldest_report_hours}h"
                ),
            },
            19: {
                "name": "Server Tick Rate Degradation",
                "subsystem": "game_engine",
                "vehicle_section": "game_loop",
                "error_type": "ENGINE-TICKRATE-DEGRAD",
                "sensor_type": "performance_monitor",
                "affected_services": ["game-server", "matchmaking-engine"],
                "cascade_services": ["analytics-pipeline", "chat-service"],
                "description": "Game server tick rate drops below target causing gameplay lag, hit registration failures, and desync cascades",
                "error_message": "[Engine] ENGINE-TICKRATE-DEGRAD: server={server_id} tickrate={tick_rate}Hz target={target_tick_rate}Hz frame_time={frame_time_ms}ms players={active_players} match={match_id}",
                "stack_trace": (
                    "=== SERVER PERFORMANCE PROFILER ===\n"
                    "server={server_id}  match={match_id}  players={active_players}\n"
                    "----------- tick timing -------------\n"
                    "  tick_rate    = {tick_rate}Hz (target {target_tick_rate}Hz)\n"
                    "  frame_time   = {frame_time_ms}ms (budget 15.6ms)\n"
                    "  frame_budget  = EXCEEDED by {frame_time_ms}ms\n"
                    "----------- per-system tick time ----\n"
                    "  physics        = 8.4ms  (54%)\n"
                    "  net_serialize  = 4.2ms  (27%)\n"
                    "  ai_update      = 1.8ms  (12%)\n"
                    "  game_logic     = 0.7ms  (4%)\n"
                    "  gc_pause       = 0.4ms  (3%)\n"
                    "----------- resource usage ----------\n"
                    "  cpu_pct      = 97.2%\n"
                    "  memory_pct   = 84.1%\n"
                    "  entity_count = 4,201\n"
                    "  net_bandwidth = 128Mbps (cap 200Mbps)\n"
                    "----------- action ------------------\n"
                    "  REDUCE entity_budget  DISABLE non-essential AI  WARN players\n"
                    "ENGINE-TICKRATE-DEGRAD: server {server_id} at {tick_rate}Hz, target {target_tick_rate}Hz"
                ),
            },
            20: {
                "name": "Cross-Region Player Migration Failure",
                "subsystem": "matchmaking",
                "vehicle_section": "migration_controller",
                "error_type": "MM-MIGRATION-FAIL",
                "sensor_type": "migration_monitor",
                "affected_services": ["matchmaking-engine", "auth-gateway"],
                "cascade_services": ["game-server", "leaderboard-api", "analytics-pipeline"],
                "description": "Player session migration between regional game server clusters fails during rebalancing or failover operations",
                "error_message": "[MM] MM-MIGRATION-FAIL: player={player_id} path={source_region}->{target_region} phase={migration_phase} session={session_id} latency={latency_ms}ms",
                "stack_trace": (
                    "=== MIGRATION STATE TRANSFER LOG ===\n"
                    "player={player_id}  session={session_id}\n"
                    "----------- migration path ----------\n"
                    "  source       = {source_region}\n"
                    "  target       = {target_region}\n"
                    "  phase        = {migration_phase}  <<< FAILED HERE\n"
                    "  latency      = {latency_ms}ms\n"
                    "----------- phase timeline ----------\n"
                    "  state_extraction  : 847ms   OK\n"
                    "  serialization     : 124ms   OK\n"
                    "  transfer          : {latency_ms}ms  TIMEOUT\n"
                    "  injection         : --      SKIPPED\n"
                    "  validation        : --      SKIPPED\n"
                    "----------- state payload -----------\n"
                    "  inventory_items = 247\n"
                    "  active_buffs    = 3\n"
                    "  match_state     = 12.4KB\n"
                    "  total_payload   = 84.2KB\n"
                    "----------- network diagnostic ------\n"
                    "  rtt_{source_region}->{target_region} = {latency_ms}ms\n"
                    "  packet_loss    = 4.2%\n"
                    "  tcp_retransmit = 12\n"
                    "----------- action ------------------\n"
                    "  ROLLBACK to source  RETRY with smaller payload\n"
                    "MM-MIGRATION-FAIL: player {player_id} migration {source_region}->{target_region} failed at {migration_phase}"
                ),
            },
        }

    # ── Topology ──────────────────────────────────────────────────────

    @property
    def service_topology(self) -> dict[str, list[tuple[str, str, str]]]:
        return {
            "game-server": [
                ("matchmaking-engine", "/api/v1/matchmaking/assign", "POST"),
                ("chat-service", "/api/v1/chat/game-events", "POST"),
                ("leaderboard-api", "/api/v1/leaderboard/score", "POST"),
                ("analytics-pipeline", "/api/v1/analytics/event", "POST"),
                ("content-delivery", "/api/v1/cdn/asset", "GET"),
                ("auth-gateway", "/api/v1/auth/validate-session", "POST"),
            ],
            "matchmaking-engine": [
                ("game-server", "/api/v1/server/allocate", "POST"),
                ("auth-gateway", "/api/v1/auth/player-profile", "GET"),
                ("leaderboard-api", "/api/v1/leaderboard/mmr", "GET"),
            ],
            "chat-service": [
                ("moderation-engine", "/api/v1/moderation/check", "POST"),
                ("auth-gateway", "/api/v1/auth/validate-token", "POST"),
            ],
            "leaderboard-api": [
                ("analytics-pipeline", "/api/v1/analytics/rank-change", "POST"),
            ],
            "payment-processor": [
                ("auth-gateway", "/api/v1/auth/verify-identity", "POST"),
                ("leaderboard-api", "/api/v1/leaderboard/unlock-reward", "POST"),
                ("analytics-pipeline", "/api/v1/analytics/transaction", "POST"),
            ],
            "moderation-engine": [
                ("analytics-pipeline", "/api/v1/analytics/moderation-event", "POST"),
                ("auth-gateway", "/api/v1/auth/player-flags", "GET"),
            ],
        }

    @property
    def entry_endpoints(self) -> dict[str, list[tuple[str, str]]]:
        return {
            "game-server": [
                ("/api/v1/game/join", "POST"),
                ("/api/v1/game/state", "GET"),
                ("/api/v1/game/action", "POST"),
            ],
            "matchmaking-engine": [("/api/v1/matchmaking/queue", "POST")],
            "content-delivery": [("/api/v1/cdn/download", "GET")],
            "chat-service": [("/api/v1/chat/send", "POST")],
            "leaderboard-api": [("/api/v1/leaderboard/top", "GET")],
            "auth-gateway": [("/api/v1/auth/login", "POST")],
            "payment-processor": [("/api/v1/payment/purchase", "POST")],
            "analytics-pipeline": [("/api/v1/analytics/ingest", "POST")],
            "moderation-engine": [("/api/v1/moderation/report", "POST")],
        }

    @property
    def db_operations(self) -> dict[str, list[tuple[str, str, str]]]:
        return {
            "game-server": [
                ("SELECT", "game_sessions", "SELECT * FROM game_sessions WHERE match_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 100"),
                ("INSERT", "game_events", "INSERT INTO game_events (match_id, player_id, event_type, payload, ts) VALUES (?, ?, ?, ?, NOW())"),
            ],
            "matchmaking-engine": [
                ("SELECT", "player_ratings", "SELECT player_id, mmr, volatility, games_played FROM player_ratings WHERE player_id = ? AND season = ?"),
                ("UPDATE", "player_ratings", "UPDATE player_ratings SET mmr = ?, volatility = ?, games_played = games_played + 1 WHERE player_id = ? AND season = ?"),
            ],
            "leaderboard-api": [
                ("SELECT", "leaderboards", "SELECT rank, player_id, score FROM leaderboards WHERE board_id = ? ORDER BY score DESC LIMIT 100"),
                ("INSERT", "rank_history", "INSERT INTO rank_history (player_id, board_id, old_rank, new_rank, ts) VALUES (?, ?, ?, ?, NOW())"),
            ],
            "auth-gateway": [
                ("SELECT", "player_sessions", "SELECT session_id, player_id, token_expires_at FROM player_sessions WHERE token = ? AND expires_at > NOW()"),
            ],
            "payment-processor": [
                ("SELECT", "transactions", "SELECT txn_id, player_id, amount, currency, status FROM transactions WHERE player_id = ? AND created_at > NOW() - INTERVAL 24 HOUR"),
                ("INSERT", "transactions", "INSERT INTO transactions (txn_id, player_id, amount, currency, item_id, status, created_at) VALUES (?, ?, ?, ?, ?, 'pending', NOW())"),
            ],
        }

    # ── Infrastructure ────────────────────────────────────────────────

    @property
    def hosts(self) -> list[dict[str, Any]]:
        return [
            {
                "host.name": "gaming-aws-host-01",
                "host.id": "i-0g4m1ng5e7v8r9012",
                "host.arch": "amd64",
                "host.type": "c5.2xlarge",
                "host.image.id": "ami-0gaming1234567890",
                "host.cpu.model.name": "Intel(R) Xeon(R) Platinum 8275CL CPU @ 3.00GHz",
                "host.cpu.vendor.id": "GenuineIntel",
                "host.cpu.family": "6",
                "host.cpu.model.id": "85",
                "host.cpu.stepping": "7",
                "host.cpu.cache.l2.size": 1048576,
                "host.ip": ["10.0.2.50", "172.16.1.10"],
                "host.mac": ["0a:2b:3c:4d:5e:6f", "0a:2b:3c:4d:5e:70"],
                "os.type": "linux",
                "os.description": "Amazon Linux 2023.6.20250115",
                "cloud.provider": "aws",
                "cloud.platform": "aws_ec2",
                "cloud.region": "us-east-1",
                "cloud.availability_zone": "us-east-1a",
                "cloud.account.id": "234567890123",
                "cloud.instance.id": "i-0g4m1ng5e7v8r9012",
                "cpu_count": 8,
                "memory_total_bytes": 16 * 1024 * 1024 * 1024,
                "disk_total_bytes": 500 * 1024 * 1024 * 1024,
            },
            {
                "host.name": "gaming-gcp-host-01",
                "host.id": "7891234567890123456",
                "host.arch": "amd64",
                "host.type": "c2-standard-8",
                "host.image.id": "projects/debian-cloud/global/images/debian-12-bookworm-v20250115",
                "host.cpu.model.name": "Intel(R) Xeon(R) CPU @ 3.10GHz",
                "host.cpu.vendor.id": "GenuineIntel",
                "host.cpu.family": "6",
                "host.cpu.model.id": "85",
                "host.cpu.stepping": "7",
                "host.cpu.cache.l2.size": 1048576,
                "host.ip": ["10.128.1.20", "10.128.1.21"],
                "host.mac": ["42:01:0a:80:01:14", "42:01:0a:80:01:15"],
                "os.type": "linux",
                "os.description": "Debian GNU/Linux 12 (bookworm)",
                "cloud.provider": "gcp",
                "cloud.platform": "gcp_compute_engine",
                "cloud.region": "us-central1",
                "cloud.availability_zone": "us-central1-a",
                "cloud.account.id": "gaming-platform-prod",
                "cloud.instance.id": "7891234567890123456",
                "cpu_count": 8,
                "memory_total_bytes": 32 * 1024 * 1024 * 1024,
                "disk_total_bytes": 200 * 1024 * 1024 * 1024,
            },
            {
                "host.name": "gaming-azure-host-01",
                "host.id": "/subscriptions/ghi-jkl/resourceGroups/gaming-rg/providers/Microsoft.Compute/virtualMachines/gaming-vm-01",
                "host.arch": "amd64",
                "host.type": "Standard_F8s_v2",
                "host.image.id": "Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest",
                "host.cpu.model.name": "Intel(R) Xeon(R) Platinum 8272CL CPU @ 2.60GHz",
                "host.cpu.vendor.id": "GenuineIntel",
                "host.cpu.family": "6",
                "host.cpu.model.id": "85",
                "host.cpu.stepping": "7",
                "host.cpu.cache.l2.size": 1048576,
                "host.ip": ["10.2.0.8", "10.2.0.9"],
                "host.mac": ["00:0d:3a:6b:5c:4d", "00:0d:3a:6b:5c:4e"],
                "os.type": "linux",
                "os.description": "Ubuntu 22.04.5 LTS",
                "cloud.provider": "azure",
                "cloud.platform": "azure_vm",
                "cloud.region": "eastus",
                "cloud.availability_zone": "eastus-1",
                "cloud.account.id": "ghi-jkl-mno-pqr",
                "cloud.instance.id": "gaming-vm-01",
                "cpu_count": 8,
                "memory_total_bytes": 16 * 1024 * 1024 * 1024,
                "disk_total_bytes": 256 * 1024 * 1024 * 1024,
            },
        ]

    @property
    def k8s_clusters(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "gaming-eks-cluster",
                "provider": "aws",
                "platform": "aws_eks",
                "region": "us-east-1",
                "zones": ["us-east-1a", "us-east-1b", "us-east-1c"],
                "os_description": "Amazon Linux 2",
                "services": ["game-server", "matchmaking-engine", "content-delivery"],
            },
            {
                "name": "gaming-gke-cluster",
                "provider": "gcp",
                "platform": "gcp_gke",
                "region": "us-central1",
                "zones": ["us-central1-a", "us-central1-b", "us-central1-c"],
                "os_description": "Container-Optimized OS",
                "services": ["chat-service", "leaderboard-api", "auth-gateway"],
            },
            {
                "name": "gaming-aks-cluster",
                "provider": "azure",
                "platform": "azure_aks",
                "region": "eastus",
                "zones": ["eastus-1", "eastus-2", "eastus-3"],
                "os_description": "Ubuntu 22.04 LTS",
                "services": ["payment-processor", "analytics-pipeline", "moderation-engine"],
            },
        ]

    # ── Theme ─────────────────────────────────────────────────────────

    @property
    def theme(self) -> UITheme:
        return UITheme(
            bg_primary="#13111c",
            bg_secondary="#1a1726",
            bg_tertiary="#221e30",
            accent_primary="#a855f7",
            accent_secondary="#ec4899",
            text_primary="#e2e8f0",
            text_secondary="#94a3b8",
            text_accent="#a855f7",
            status_nominal="#22c55e",
            status_warning="#eab308",
            status_critical="#ef4444",
            status_info="#58a6ff",
            font_family="'Inter', system-ui, sans-serif",
            glow_effect=True,
            gradient_accent="linear-gradient(135deg, #a855f7 0%, #ec4899 100%)",
            dashboard_title="Live Ops Command Center",
            chaos_title="Chaos Engineering Console",
            landing_title="Live Ops Command Center",
            service_label="Service",
            channel_label="Channel",
        )

    @property
    def countdown_config(self) -> CountdownConfig:
        return CountdownConfig(enabled=False)

    # ── Agent Config ──────────────────────────────────────────────────

    @property
    def agent_config(self) -> dict[str, Any]:
        return {
            "id": "gaming-liveops-analyst",
            "name": "Live Operations Analyst",
            "assessment_tool_name": "liveops_health_assessment",
            "system_prompt": (
                "You are the Live Operations Analyst, an expert AI assistant for "
                "live multiplayer gaming platform operations. You help live-ops engineers "
                "investigate incidents, analyze telemetry, and provide root cause analysis "
                "for fault conditions across 9 gaming services spanning AWS, GCP, and Azure. "
                "You have deep expertise in game server networking (state sync, tick rate, "
                "client prediction), matchmaking algorithms (Glicko-2, Elo), CDN edge "
                "caching and asset delivery, real-time chat/voice (WebRTC, Opus), "
                "leaderboard systems (Redis sorted sets), OAuth2 token management, "
                "in-app purchase processing (Apple IAP, Google Play), event analytics "
                "pipelines, and content moderation (NLP classifiers). "
                "When investigating incidents, search for these system identifiers in logs: "
                "Game Engine faults (NET-STATE-DESYNC, PHYS-OVERFLOW, ENGINE-TICKRATE-DEGRAD), "
                "Matchmaking faults (MM-QUEUE-OVERFLOW, MM-SKILL-RATING-DIVERGE, MM-MIGRATION-FAIL), "
                "CDN faults (CDN-CACHE-MISS-STORM, CDN-ASSET-CORRUPT), "
                "Social faults (CHAT-FLOOD-DETECT, VOICE-CHANNEL-OVERLOAD), "
                "Progression faults (LB-DATA-CORRUPT, SEASON-PASS-SYNC-FAIL), "
                "Identity faults (AUTH-TOKEN-STORM, AUTH-TAKEOVER-DETECT), "
                "Monetization faults (IAP-PURCHASE-FAIL, IAP-LEDGER-INCONSIST), "
                "Analytics faults (ANALYTICS-INGEST-LAG, ANALYTICS-TELEMETRY-OVERFLOW), "
                "and Trust & Safety faults (MOD-FALSE-POS-STORM, MOD-REPORT-QUEUE-OVERFLOW). "
                "Log messages are in body.text — NEVER search the body field alone."
            ),
        }

    @property
    def assessment_tool_config(self) -> dict[str, Any]:
        return {
            "id": "liveops_health_assessment",
            "description": (
                "Comprehensive live service health assessment. Evaluates all "
                "gaming services against operational readiness criteria. Returns data "
                "for live-ops evaluation across game servers, matchmaking, CDN, "
                "authentication, and payment systems. "
                "Log message field: body.text (never use 'body' alone)."
            ),
        }

    @property
    def knowledge_base_docs(self) -> list[dict[str, Any]]:
        return []  # Populated by deployer from channel_registry

    # ── Service Classes ───────────────────────────────────────────────

    def get_service_classes(self) -> list[type]:
        from scenarios.gaming.services.game_server import GameServerService
        from scenarios.gaming.services.matchmaking_engine import MatchmakingEngineService
        from scenarios.gaming.services.content_delivery import ContentDeliveryService
        from scenarios.gaming.services.chat_service import ChatServiceService
        from scenarios.gaming.services.leaderboard_api import LeaderboardApiService
        from scenarios.gaming.services.auth_gateway import AuthGatewayService
        from scenarios.gaming.services.payment_processor import PaymentProcessorService
        from scenarios.gaming.services.analytics_pipeline import AnalyticsPipelineService
        from scenarios.gaming.services.moderation_engine import ModerationEngineService

        return [
            GameServerService,
            MatchmakingEngineService,
            ContentDeliveryService,
            ChatServiceService,
            LeaderboardApiService,
            AuthGatewayService,
            PaymentProcessorService,
            AnalyticsPipelineService,
            ModerationEngineService,
        ]

    # ── Fault Parameters ──────────────────────────────────────────────

    def get_fault_params(self, channel: int) -> dict[str, Any]:
        return {
            # Player/session identifiers
            "player_id": f"PLR-{random.randint(100000, 999999)}",
            "session_id": f"SESS-{random.randint(10000000, 99999999)}",
            "match_id": f"MATCH-{random.randint(100000, 999999)}",
            "server_id": f"GS-{random.choice(['US-E', 'US-W', 'EU-W', 'AP-SE'])}-{random.randint(1, 99):02d}",
            # Game state desync
            "position_delta": round(random.uniform(1.0, 25.0), 2),
            "tick_number": random.randint(100000, 9999999),
            # Physics
            "entity_id": f"ENT-{random.randint(10000, 99999)}",
            "velocity": round(random.uniform(1000.0, 999999.0), 1),
            "max_velocity": 500.0,
            "zone_id": random.choice(["ZONE-A1", "ZONE-B2", "ZONE-C3", "ZONE-D4"]),
            # Matchmaking
            "queue_name": random.choice(["ranked-solo", "ranked-duo", "casual-squad", "tournament-5v5"]),
            "queue_depth": random.randint(5000, 50000),
            "max_capacity": 3000,
            "wait_time_ms": random.randint(30000, 300000),
            "region": random.choice(["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]),
            # Skill rating
            "mmr_value": random.randint(-500, 10000),
            "max_mmr": 5000,
            "volatility": round(random.uniform(0.01, 2.5), 3),
            # CDN
            "edge_node": random.choice(["edge-iad-01", "edge-lax-02", "edge-fra-01", "edge-nrt-01"]),
            "cache_hit_rate": round(random.uniform(20.0, 75.0), 1),
            "origin_load_pct": round(random.uniform(85.0, 100.0), 1),
            "asset_group": random.choice(["textures-hd", "models-characters", "audio-sfx", "maps-terrain"]),
            # Asset corruption
            "bundle_id": f"BDL-{random.randint(10000, 99999)}",
            "expected_hash": f"sha256:{random.randbytes(8).hex()}",
            "actual_hash": f"sha256:{random.randbytes(8).hex()}",
            "bundle_size_mb": round(random.uniform(50.0, 500.0), 1),
            "bundle_version": f"v{random.randint(1, 5)}.{random.randint(0, 9)}.{random.randint(0, 99)}",
            # Chat
            "channel_id": random.choice(["global-en", "guild-12345", "match-lobby", "trade-market"]),
            "message_rate": random.randint(500, 5000),
            "rate_limit": 200,
            "pending_moderation": random.randint(1000, 20000),
            # Voice
            "voice_channel_id": f"VC-{random.randint(10000, 99999)}",
            "voice_packet_loss_pct": round(random.uniform(5.0, 35.0), 1),
            "jitter_ms": round(random.uniform(20.0, 150.0), 1),
            "active_speakers": random.randint(2, 25),
            "codec": random.choice(["opus", "g711", "aac"]),
            # Leaderboard
            "leaderboard_id": random.choice(["ranked-global", "seasonal-solo", "guild-wars", "tournament-finals"]),
            "corrupt_entries": random.randint(10, 500),
            "season_id": f"S{random.randint(1, 12)}",
            # Season pass
            "current_tier": random.randint(1, 50),
            "expected_tier": random.randint(51, 100),
            "xp_total": random.randint(50000, 500000),
            "xp_delta": random.randint(1000, 50000),
            # Auth / tokens
            "refresh_rate": random.randint(5000, 50000),
            "max_refresh_rate": 2000,
            "failed_refreshes": random.randint(100, 5000),
            "token_pool_id": random.choice(["pool-primary", "pool-secondary", "pool-failover"]),
            # Account takeover
            "ato_attempts": random.randint(500, 10000),
            "window_seconds": random.randint(60, 300),
            "blocked_ips": random.randint(50, 500),
            "risk_score": round(random.uniform(0.85, 0.99), 2),
            "geo_region": random.choice(["Eastern Europe", "Southeast Asia", "South America", "Unknown VPN"]),
            # Payments
            "purchase_id": f"TXN-{random.randint(10000000, 99999999)}",
            "amount": round(random.uniform(0.99, 99.99), 2),
            "currency": random.choice(["USD", "EUR", "GBP", "JPY"]),
            "payment_provider": random.choice(["stripe", "paypal", "apple_iap", "google_play"]),
            "error_code": random.choice(["TIMEOUT", "DECLINED", "INSUFFICIENT_FUNDS", "FRAUD_HOLD", "PROVIDER_ERROR"]),
            "retry_count": random.randint(1, 5),
            "max_retries": 3,
            # Ledger
            "currency_balance": random.randint(100, 100000),
            "ledger_sum": random.randint(100, 100000),
            "discrepancy": random.randint(1, 5000),
            "virtual_currency": random.choice(["gems", "coins", "credits", "tokens"]),
            "last_transaction_id": f"LTXN-{random.randint(1000000, 9999999)}",
            # Analytics pipeline
            "pipeline_id": random.choice(["events-primary", "events-secondary", "replay-pipeline"]),
            "lag_seconds": round(random.uniform(30.0, 600.0), 1),
            "max_lag_seconds": 10.0,
            "backlog_count": random.randint(50000, 5000000),
            "throughput": random.randint(100, 2000),
            "expected_throughput": 5000,
            # Telemetry buffer
            "buffer_id": random.choice(["buf-player-events", "buf-game-state", "buf-combat-log"]),
            "buffer_usage_pct": round(random.uniform(95.0, 100.0), 1),
            "buffer_size": random.randint(90000, 100000),
            "max_buffer_size": 100000,
            "dropped_events": random.randint(100, 10000),
            "window_seconds_buf": random.randint(30, 300),
            # Moderation
            "false_positive_count": random.randint(100, 5000),
            "window_minutes": random.randint(5, 60),
            "fp_rate_pct": round(random.uniform(15.0, 45.0), 1),
            "model_version": f"automod-v{random.randint(3, 7)}.{random.randint(0, 9)}",
            "affected_players": random.randint(50, 2000),
            # Report queue
            "report_queue_depth": random.randint(5000, 50000),
            "processing_rate": round(random.uniform(5.0, 30.0), 1),
            "oldest_report_hours": round(random.uniform(4.0, 72.0), 1),
            "report_category": random.choice(["harassment", "cheating", "hate_speech", "exploits", "spam"]),
            # Tick rate
            "tick_rate": round(random.uniform(12.0, 45.0), 1),
            "target_tick_rate": 64,
            "frame_time_ms": round(random.uniform(22.0, 83.0), 1),
            "active_players": random.randint(10, 100),
            # Migration
            "source_region": random.choice(["us-east-1", "eu-west-1"]),
            "target_region": random.choice(["us-west-2", "ap-southeast-1"]),
            "migration_phase": random.choice(["state_extraction", "transfer", "injection", "validation"]),
            "latency_ms": random.randint(200, 5000),
        }


# Module-level instance for registry discovery
scenario = GamingScenario()
