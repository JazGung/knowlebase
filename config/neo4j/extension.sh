# EXTENSION_SCRIPT 钩子 — 在 entrypoint 所有初始化完成后、neo4j console 启动前执行
# 清理 store_lock 防止 "Neo4j is already running" 误判
rm -f /data/databases/store_lock /data/dbms/*.pid /data/locks/*.lock 2>/dev/null
