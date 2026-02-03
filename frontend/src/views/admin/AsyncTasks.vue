<template>
  <div class="space-y-6 pb-8">
    <!-- 统计卡片 -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <Card variant="default" class="p-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <Zap class="w-5 h-5 text-primary" />
          </div>
          <div>
            <p class="text-2xl font-bold">{{ stats?.total ?? '-' }}</p>
            <p class="text-xs text-muted-foreground">总任务数</p>
          </div>
        </div>
      </Card>
      <Card variant="default" class="p-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <Loader2 class="w-5 h-5 text-blue-500" :class="{ 'animate-spin': (stats?.processing_count ?? 0) > 0 }" />
          </div>
          <div>
            <p class="text-2xl font-bold">{{ stats?.processing_count ?? stats?.by_status?.processing ?? '-' }}</p>
            <p class="text-xs text-muted-foreground">处理中</p>
          </div>
        </div>
      </Card>
      <Card variant="default" class="p-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
            <CheckCircle class="w-5 h-5 text-green-500" />
          </div>
          <div>
            <p class="text-2xl font-bold">{{ stats?.by_status?.completed ?? '-' }}</p>
            <p class="text-xs text-muted-foreground">已完成</p>
          </div>
        </div>
      </Card>
      <Card variant="default" class="p-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
            <Calendar class="w-5 h-5 text-amber-500" />
          </div>
          <div>
            <p class="text-2xl font-bold">{{ stats?.today_count ?? '-' }}</p>
            <p class="text-xs text-muted-foreground">今日任务</p>
          </div>
        </div>
      </Card>
    </div>

    <!-- 任务表格 -->
    <Card variant="default" class="overflow-hidden">
      <!-- 标题和筛选器 -->
      <div class="px-4 sm:px-6 py-3.5 border-b border-border/60">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h3 class="text-base font-semibold">异步任务</h3>
          <div class="flex items-center gap-2">
            <!-- 状态筛选 -->
            <Select v-model="filterStatus">
              <SelectTrigger class="w-28 h-8 text-xs border-border/60">
                <SelectValue placeholder="状态" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="submitted">已提交</SelectItem>
                <SelectItem value="processing">处理中</SelectItem>
                <SelectItem value="completed">已完成</SelectItem>
                <SelectItem value="failed">失败</SelectItem>
                <SelectItem value="cancelled">已取消</SelectItem>
              </SelectContent>
            </Select>
            <!-- 模型筛选 -->
            <Input
              v-model="filterModel"
              type="text"
              placeholder="模型..."
              class="w-32 h-8 text-xs"
            />
            <!-- 刷新按钮 -->
            <Button
              variant="ghost"
              size="icon"
              class="h-8 w-8"
              :disabled="loading"
              @click="fetchTasks"
            >
              <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': loading }" />
            </Button>
          </div>
        </div>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading && !tasks.length" class="p-8 text-center">
        <Loader2 class="w-8 h-8 animate-spin mx-auto text-muted-foreground" />
        <p class="mt-2 text-sm text-muted-foreground">加载中...</p>
      </div>

      <!-- 空状态 -->
      <div v-else-if="!tasks.length" class="p-8 text-center">
        <Zap class="w-12 h-12 mx-auto text-muted-foreground/50" />
        <p class="mt-2 text-sm text-muted-foreground">暂无异步任务</p>
      </div>

      <!-- 桌面端表格 -->
      <Table v-else class="hidden md:table">
        <TableHeader>
          <TableRow>
            <TableHead class="w-[25%]">任务</TableHead>
            <TableHead class="w-[15%]">用户/Provider</TableHead>
            <TableHead class="w-[12%]">状态</TableHead>
            <TableHead class="w-[10%]">参数</TableHead>
            <TableHead class="w-[15%]">时间</TableHead>
            <TableHead class="w-[8%] text-center">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow
            v-for="task in tasks"
            :key="task.id"
            class="cursor-pointer hover:bg-muted/50"
            @click="openTaskDetail(task)"
          >
            <!-- 任务信息 -->
            <TableCell>
              <div class="space-y-1">
                <div class="flex items-center gap-2">
                  <Video v-if="isVideoTask(task)" class="w-4 h-4 text-muted-foreground shrink-0" />
                  <span class="font-medium text-sm truncate">{{ task.model }}</span>
                </div>
                <p class="text-xs text-muted-foreground truncate max-w-[280px]" :title="task.prompt">
                  {{ task.prompt }}
                </p>
              </div>
            </TableCell>
            <!-- 用户/Provider -->
            <TableCell>
              <div class="space-y-0.5 text-sm">
                <div class="flex items-center gap-1.5">
                  <User class="w-3 h-3 text-muted-foreground" />
                  <span class="truncate max-w-[100px]">{{ task.username }}</span>
                </div>
                <div class="flex items-center gap-1.5 text-muted-foreground">
                  <Server class="w-3 h-3" />
                  <span class="truncate max-w-[100px]">{{ task.provider_name }}</span>
                </div>
              </div>
            </TableCell>
            <!-- 状态 -->
            <TableCell>
              <div class="flex flex-col items-start gap-1">
                <Badge :variant="getStatusVariant(task.status)" class="text-xs">
                  {{ getStatusLabel(task.status) }}
                </Badge>
                <div v-if="task.progress_percent > 0 && task.status === 'processing'" class="w-full">
                  <div class="flex items-center gap-2">
                    <div class="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        class="h-full bg-primary transition-all"
                        :style="{ width: `${task.progress_percent}%` }"
                      />
                    </div>
                    <span class="text-xs text-muted-foreground">{{ task.progress_percent }}%</span>
                  </div>
                </div>
              </div>
            </TableCell>
            <!-- 参数 -->
            <TableCell>
              <div class="text-xs space-y-0.5 text-muted-foreground">
                <div v-if="task.duration_seconds" class="flex items-center gap-1">
                  <Timer class="w-3 h-3" />
                  <span>{{ task.duration_seconds }}s</span>
                </div>
                <div v-if="task.resolution">{{ task.resolution }}</div>
                <div v-if="task.aspect_ratio">{{ task.aspect_ratio }}</div>
              </div>
            </TableCell>
            <!-- 时间 -->
            <TableCell>
              <div class="text-xs space-y-0.5">
                <div class="flex items-center gap-1.5 text-muted-foreground">
                  <Clock class="w-3 h-3" />
                  <span>{{ formatDate(task.created_at) }}</span>
                </div>
                <div v-if="task.completed_at" class="flex items-center gap-1.5 text-green-600 dark:text-green-400">
                  <CheckCircle class="w-3 h-3" />
                  <span>{{ formatDate(task.completed_at) }}</span>
                </div>
              </div>
            </TableCell>
            <!-- 操作 -->
            <TableCell class="text-center">
              <div class="flex items-center justify-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  class="h-7 w-7"
                  title="任务详情"
                  @click.stop="openTaskDetail(task)"
                >
                  <Eye class="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  class="h-7 w-7"
                  title="使用记录"
                  @click.stop="openUsageRecord(task)"
                >
                  <ExternalLink class="w-4 h-4" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>

      <!-- 移动端卡片列表 -->
      <div v-if="tasks.length" class="md:hidden divide-y divide-border/60">
        <div
          v-for="task in tasks"
          :key="`m-${task.id}`"
          class="p-4 space-y-3 hover:bg-muted/30 cursor-pointer active:bg-muted/50 transition-colors"
          @click="openTaskDetail(task)"
        >
          <!-- 顶部：模型和状态 -->
          <div class="flex items-start justify-between gap-2">
            <div class="flex items-center gap-2 min-w-0 flex-1">
              <Video v-if="isVideoTask(task)" class="w-4 h-4 text-muted-foreground shrink-0" />
              <span class="font-medium text-sm truncate">{{ task.model }}</span>
            </div>
            <Badge :variant="getStatusVariant(task.status)" class="text-xs shrink-0">
              {{ getStatusLabel(task.status) }}
            </Badge>
          </div>

          <!-- 进度条（如果有） -->
          <div v-if="task.progress_percent > 0 && task.status === 'processing'" class="space-y-1">
            <div class="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                class="h-full bg-primary transition-all"
                :style="{ width: `${task.progress_percent}%` }"
              />
            </div>
            <p class="text-xs text-muted-foreground text-right">{{ task.progress_percent }}%</p>
          </div>

          <!-- Prompt -->
          <p class="text-sm text-muted-foreground line-clamp-2">{{ task.prompt }}</p>

          <!-- 信息网格 -->
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="flex items-center gap-1.5 text-muted-foreground">
              <User class="w-3 h-3" />
              <span class="truncate">{{ task.username }}</span>
            </div>
            <div class="flex items-center gap-1.5 text-muted-foreground">
              <Server class="w-3 h-3" />
              <span class="truncate">{{ task.provider_name }}</span>
            </div>
            <div class="flex items-center gap-1.5 text-muted-foreground">
              <Clock class="w-3 h-3" />
              <span>{{ formatDate(task.created_at) }}</span>
            </div>
            <div v-if="task.duration_seconds" class="flex items-center gap-1.5 text-muted-foreground">
              <Timer class="w-3 h-3" />
              <span>{{ task.duration_seconds }}s</span>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              class="h-7 text-xs"
              @click.stop="openUsageRecord(task)"
            >
              <ExternalLink class="w-3.5 h-3.5 mr-1" />
              使用记录
            </Button>
            <Button
              v-if="canCancel(task.status)"
              variant="outline"
              size="sm"
              class="h-7 text-xs text-red-500 border-red-200 hover:bg-red-50"
              @click.stop="cancelTask(task)"
            >
              <XCircle class="w-3.5 h-3.5 mr-1" />
              取消
            </Button>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <Pagination
        v-if="total > 0"
        :current="currentPage"
        :total="total"
        :page-size="pageSize"
        cache-key="async-tasks-page-size"
        @update:current="goToPage"
        @update:page-size="handlePageSizeChange"
      />
    </Card>

    <!-- 任务详情抽屉 -->
    <Teleport to="body">
      <Transition name="drawer">
        <div
          v-if="showDetail && selectedTask"
          class="fixed inset-0 z-50 flex justify-end"
          @click.self="closeDetail"
        >
          <!-- 背景遮罩 -->
          <div
            class="absolute inset-0 bg-black/30 backdrop-blur-sm"
            @click="closeDetail"
          />
          <!-- 抽屉内容 -->
          <Card class="relative h-full w-full sm:w-[800px] sm:max-w-[90vw] rounded-none shadow-2xl flex flex-col">
            <!-- 固定头部 -->
            <div class="sticky top-0 z-10 bg-background border-b px-3 sm:px-6 py-3 sm:py-4 flex-shrink-0">
              <!-- 第一行：标题、模型、状态、操作按钮 -->
              <div class="flex items-center justify-between gap-4 mb-3">
                <div class="flex items-center gap-3 flex-wrap">
                  <h3 class="text-lg font-semibold">任务详情</h3>
                  <div class="flex items-center gap-1 text-sm font-mono text-muted-foreground bg-muted px-2 py-0.5 rounded">
                    <Video v-if="isVideoTask(selectedTask)" class="w-3.5 h-3.5 mr-1" />
                    <span>{{ selectedTask.model }}</span>
                  </div>
                  <Badge :variant="getStatusVariant(selectedTask.status)">
                    {{ getStatusLabel(selectedTask.status) }}
                  </Badge>
                </div>
                <div class="flex items-center gap-1 shrink-0">
                  <Button
                    variant="ghost"
                    size="icon"
                    class="h-8 w-8"
                    :class="{ 'text-primary': detailAutoRefresh }"
                    :title="detailAutoRefresh ? '停止自动刷新' : '开启自动刷新（每5秒）'"
                    @click="toggleDetailAutoRefresh"
                  >
                    <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': detailAutoRefresh }" />
                  </Button>
                  <Button variant="ghost" size="icon" class="h-8 w-8" title="关闭" @click="closeDetail">
                    <X class="w-4 h-4" />
                  </Button>
                </div>
              </div>
              <!-- 第二行：关键元信息 -->
              <div class="flex items-center flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span class="flex items-center gap-1">
                  <span class="font-medium text-foreground">ID:</span>
                  <span class="font-mono">{{ selectedTask.id.slice(0, 8) }}...</span>
                </span>
                <span class="opacity-40">|</span>
                <span>{{ formatDateFull(selectedTask.created_at) }}</span>
                <span class="opacity-40">|</span>
                <span>用户: {{ selectedTask.username }}</span>
                <span class="opacity-40">|</span>
                <span>Provider: {{ selectedTask.provider_name }}</span>
              </div>
              <!-- 进度条 -->
              <div v-if="selectedTask.progress_percent > 0 && selectedTask.status === 'processing'" class="mt-3">
                <div class="flex items-center gap-3">
                  <div class="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      class="h-full bg-primary transition-all"
                      :style="{ width: `${selectedTask.progress_percent}%` }"
                    />
                  </div>
                  <span class="text-xs text-muted-foreground font-medium">{{ selectedTask.progress_percent }}%</span>
                </div>
                <p v-if="selectedTask.progress_message" class="text-xs text-muted-foreground mt-1">
                  {{ selectedTask.progress_message }}
                </p>
              </div>
            </div>

            <!-- 可滚动内容区域 -->
            <div class="flex-1 min-h-0 overflow-y-auto px-3 sm:px-6 py-3 sm:py-4 space-y-5">
              <!-- 错误信息 -->
              <div v-if="selectedTask.error_message" class="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
                <div class="flex items-start gap-2">
                  <AlertCircle class="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <div>
                    <p v-if="selectedTask.error_code" class="text-xs font-medium text-red-600 dark:text-red-400 mb-1">
                      错误码: {{ selectedTask.error_code }}
                    </p>
                    <p class="text-sm text-red-600 dark:text-red-400">{{ selectedTask.error_message }}</p>
                  </div>
                </div>
              </div>

              <!-- 视频结果（放在最前面） -->
              <div v-if="selectedTask.video_url || selectedTask.video_urls?.length" class="space-y-3">
                <!-- 主视频 -->
                <div v-if="selectedTask.video_url">
                  <div class="rounded-lg overflow-hidden border border-border/60 bg-black">
                    <video
                      :src="getVideoUrl(selectedTask.id, selectedTask.video_url)"
                      controls
                      preload="none"
                      class="w-full max-h-[300px] object-contain"
                    />
                  </div>
                  <!-- 视频信息 -->
                  <div class="mt-2 space-y-2">
                    <!-- 链接 -->
                    <div class="flex items-center gap-1 p-1.5 bg-muted/50 rounded border border-border/40">
                      <code class="flex-1 text-xs text-foreground truncate px-1" :title="selectedTask.video_url">{{ selectedTask.video_url }}</code>
                      <Button
                        variant="ghost"
                        size="sm"
                        class="h-6 px-2 text-xs shrink-0"
                        @click="copyToClipboard(selectedTask.video_url)"
                      >
                        <Copy class="w-3 h-3" />
                      </Button>
                    </div>
                    <!-- 元信息 -->
                    <div v-if="selectedTask.video_size_bytes || selectedTask.video_expires_at" class="flex items-center gap-3 text-xs text-muted-foreground">
                      <span v-if="selectedTask.video_size_bytes">
                        大小: {{ formatFileSize(selectedTask.video_size_bytes) }}
                      </span>
                      <span v-if="selectedTask.video_expires_at" class="text-amber-600 dark:text-amber-400">
                        过期: {{ formatDate(selectedTask.video_expires_at) }}
                      </span>
                    </div>
                  </div>
                </div>

                <!-- 多个视频 -->
                <div v-else-if="selectedTask.video_urls?.length" class="space-y-4">
                  <div v-for="(url, index) in selectedTask.video_urls" :key="index">
                    <p class="text-xs text-muted-foreground font-medium mb-1.5">视频 {{ index + 1 }}</p>
                    <div class="rounded-lg overflow-hidden border border-border/60 bg-black">
                      <video :src="getVideoUrl(selectedTask.id, url)" controls preload="none" class="w-full max-h-[250px] object-contain" />
                    </div>
                    <div class="mt-1.5 flex items-center gap-1 p-1.5 bg-muted/50 rounded border border-border/40">
                      <code class="flex-1 text-xs text-foreground truncate px-1" :title="url">{{ url }}</code>
                      <Button
                        variant="ghost"
                        size="sm"
                        class="h-6 px-2 text-xs shrink-0"
                        @click="copyToClipboard(url)"
                      >
                        <Copy class="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 任务完成但无视频 -->
              <div v-else-if="selectedTask.status === 'completed'" class="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800 text-center">
                <Video class="w-8 h-8 mx-auto mb-2 text-amber-500" />
                <p class="text-sm text-amber-600 dark:text-amber-400">视频链接不可用或已过期</p>
              </div>

              <!-- Prompt -->
              <div class="space-y-2">
                <div class="flex items-center justify-between">
                  <h4 class="text-xs font-medium text-muted-foreground uppercase tracking-wide">Prompt</h4>
                  <Button
                    variant="outline"
                    size="sm"
                    class="h-6 px-2 text-xs"
                    @click="copyToClipboard(selectedTask.prompt)"
                  >
                    <Copy class="w-3 h-3 mr-1" />
                    复制
                  </Button>
                </div>
                <div class="p-3 bg-muted/50 rounded-lg border border-border/60 text-sm whitespace-pre-wrap break-words max-h-32 overflow-y-auto leading-relaxed">
                  {{ selectedTask.prompt }}
                </div>
              </div>

              <!-- 视频信息（网格布局） -->
              <div v-if="selectedTask.video_duration_seconds || selectedTask.resolution || selectedTask.aspect_ratio || selectedTask.size" class="space-y-2">
                <h4 class="text-xs font-medium text-muted-foreground uppercase tracking-wide">视频信息</h4>
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div v-if="selectedTask.video_duration_seconds" class="p-3 bg-muted/30 rounded-lg">
                    <p class="text-xs text-muted-foreground mb-0.5">视频时长</p>
                    <p class="text-sm font-medium">{{ selectedTask.video_duration_seconds.toFixed(1) }}s</p>
                  </div>
                  <div v-if="selectedTask.resolution" class="p-3 bg-muted/30 rounded-lg">
                    <p class="text-xs text-muted-foreground mb-0.5">分辨率</p>
                    <p class="text-sm font-medium">{{ selectedTask.resolution }}</p>
                  </div>
                  <div v-if="selectedTask.aspect_ratio" class="p-3 bg-muted/30 rounded-lg">
                    <p class="text-xs text-muted-foreground mb-0.5">宽高比</p>
                    <p class="text-sm font-medium">{{ selectedTask.aspect_ratio }}</p>
                  </div>
                  <div v-if="selectedTask.size" class="p-3 bg-muted/30 rounded-lg">
                    <p class="text-xs text-muted-foreground mb-0.5">尺寸</p>
                    <p class="text-sm font-medium">{{ selectedTask.size }}</p>
                  </div>
                </div>
              </div>

              <!-- 执行状态（网格布局） -->
              <div class="space-y-2">
                <h4 class="text-xs font-medium text-muted-foreground uppercase tracking-wide">执行状态</h4>
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div class="p-3 bg-muted/30 rounded-lg">
                    <p class="text-xs text-muted-foreground mb-0.5">轮询</p>
                    <p class="text-sm font-medium">{{ selectedTask.poll_count }} / {{ selectedTask.max_poll_count }}</p>
                  </div>
                  <div class="p-3 bg-muted/30 rounded-lg">
                    <p class="text-xs text-muted-foreground mb-0.5">重试</p>
                    <p class="text-sm font-medium">{{ selectedTask.retry_count }} / {{ selectedTask.max_retries }}</p>
                  </div>
                  <div class="p-3 bg-muted/30 rounded-lg">
                    <p class="text-xs text-muted-foreground mb-0.5">轮询间隔</p>
                    <p class="text-sm font-medium">{{ selectedTask.poll_interval_seconds }}s</p>
                  </div>
                  <div v-if="selectedTask.next_poll_at" class="p-3 bg-muted/30 rounded-lg">
                    <p class="text-xs text-muted-foreground mb-0.5">下次轮询</p>
                    <p class="text-sm font-medium">{{ formatDate(selectedTask.next_poll_at) }}</p>
                  </div>
                </div>
              </div>

              <!-- 时间范围 -->
              <div class="space-y-2">
                <h4 class="text-xs font-medium text-muted-foreground uppercase tracking-wide">时间范围</h4>
                <div class="flex items-center gap-1 text-sm font-medium">
                  <span>{{ formatTimeWithMs(selectedTask.created_at) }}</span>
                  <span class="time-arrow-container">
                    <span v-if="selectedTask.completed_at" class="time-duration">+{{ calcDuration(selectedTask.created_at, selectedTask.completed_at) }}</span>
                    <span class="time-arrow">→</span>
                  </span>
                  <template v-if="selectedTask.completed_at">
                    <span>{{ formatTimeWithMs(selectedTask.completed_at) }}</span>
                  </template>
                  <span v-else class="text-muted-foreground">处理中...</span>
                </div>
              </div>

              <!-- 响应数据 -->
              <div v-if="selectedTask.request_metadata?.poll_raw_response" class="space-y-2">
                <div class="flex items-center justify-between">
                  <h4 class="text-xs font-medium text-muted-foreground uppercase tracking-wide flex items-center gap-2">
                    <FileJson class="w-3.5 h-3.5" />
                    响应数据
                  </h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    class="h-5 px-1.5 text-xs"
                    @click="copyToClipboard(JSON.stringify(selectedTask.request_metadata.poll_raw_response, null, 2))"
                  >
                    <Copy class="w-3 h-3 mr-1" />
                    复制
                  </Button>
                </div>
                <div class="p-3 bg-muted/50 rounded-lg border border-border/40 overflow-x-auto max-h-48 overflow-y-auto">
                  <pre class="text-xs font-mono whitespace-pre-wrap break-all text-foreground/80">{{ formatJson(selectedTask.request_metadata.poll_raw_response) }}</pre>
                </div>
              </div>

              <!-- 操作按钮 -->
              <div v-if="canCancel(selectedTask.status)" class="pt-4 border-t border-border/60">
                <Button
                  variant="destructive"
                  class="w-full"
                  @click="cancelTask(selectedTask)"
                >
                  <XCircle class="w-4 h-4 mr-2" />
                  取消任务
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </Transition>
    </Teleport>

    <!-- 使用记录详情抽屉 -->
    <RequestDetailDrawer
      :is-open="usageDetailOpen"
      :request-id="usageRequestId"
      @close="usageDetailOpen = false"
    />
  </div>
</template>

<style scoped>
.drawer-enter-active,
.drawer-leave-active {
  transition: all 0.3s ease;
}
.drawer-enter-active > div:first-child,
.drawer-leave-active > div:first-child {
  transition: opacity 0.3s ease;
}
.drawer-enter-active > div:last-child,
.drawer-leave-active > div:last-child {
  transition: transform 0.3s ease;
}
.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}
.drawer-enter-from > div:last-child,
.drawer-leave-to > div:last-child {
  transform: translateX(100%);
}

/* 时间范围箭头容器 */
.time-arrow-container {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.25rem;
}

.time-arrow {
  color: hsl(var(--muted-foreground));
}

.time-duration {
  position: absolute;
  top: -1rem;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.65rem;
  color: hsl(var(--muted-foreground));
  white-space: nowrap;
}
</style>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { asyncTasksApi, type AsyncTaskItem, type AsyncTaskDetail, type AsyncTaskStatsResponse, type AsyncTaskStatus } from '@/api/async-tasks'
import { useToast } from '@/composables/useToast'
import { useClipboard } from '@/composables/useClipboard'
import Card from '@/components/ui/card.vue'
import Button from '@/components/ui/button.vue'
import Input from '@/components/ui/input.vue'
import Badge from '@/components/ui/badge.vue'
import Select from '@/components/ui/select.vue'
import SelectTrigger from '@/components/ui/select-trigger.vue'
import SelectValue from '@/components/ui/select-value.vue'
import SelectContent from '@/components/ui/select-content.vue'
import SelectItem from '@/components/ui/select-item.vue'
import Table from '@/components/ui/table.vue'
import TableHeader from '@/components/ui/table-header.vue'
import TableBody from '@/components/ui/table-body.vue'
import TableRow from '@/components/ui/table-row.vue'
import TableHead from '@/components/ui/table-head.vue'
import TableCell from '@/components/ui/table-cell.vue'
import Pagination from '@/components/ui/pagination.vue'
import { RequestDetailDrawer } from '@/features/usage/components'
import {
  Zap,
  Video,
  Loader2,
  FileJson,
  CheckCircle,
  Calendar,
  RefreshCw,
  User,
  Server,
  Clock,
  Timer,
  XCircle,
  X,
  AlertCircle,
  Eye,
  ExternalLink,
  Copy,
} from 'lucide-vue-next'

const { toast } = useToast()
const { copyToClipboard } = useClipboard()

// 状态
const loading = ref(false)
const tasks = ref<AsyncTaskItem[]>([])
const stats = ref<AsyncTaskStatsResponse | null>(null)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const filterStatus = ref('all')
const filterModel = ref('')
const showDetail = ref(false)
const selectedTask = ref<AsyncTaskDetail | null>(null)
const detailAutoRefresh = ref(false)
let detailRefreshInterval: ReturnType<typeof setInterval> | null = null

// 使用记录详情抽屉状态
const usageDetailOpen = ref(false)
const usageRequestId = ref<string | null>(null)

// 判断是否为视频任务
function isVideoTask(task: AsyncTaskItem): boolean {
  return task.task_type === 'video' || !!task.video_url || !!task.duration_seconds
}

// 获取任务列表
async function fetchTasks() {
  loading.value = true
  try {
    const response = await asyncTasksApi.list({
      status: filterStatus.value !== 'all' ? filterStatus.value as AsyncTaskStatus : undefined,
      model: filterModel.value || undefined,
      page: currentPage.value,
      page_size: pageSize.value,
    })
    tasks.value = response.items
    total.value = response.total
  } catch (error: any) {
    toast({
      title: '获取任务列表失败',
      description: error.message,
      variant: 'destructive',
    })
  } finally {
    loading.value = false
  }
}

// 获取统计数据
async function fetchStats() {
  try {
    stats.value = await asyncTasksApi.getStats()
  } catch (error) {
    console.error('Failed to fetch stats:', error)
  }
}

// 打开任务详情
async function openTaskDetail(task: AsyncTaskItem) {
  try {
    selectedTask.value = await asyncTasksApi.getDetail(task.id)
    showDetail.value = true
  } catch (error: any) {
    toast({
      title: '获取任务详情失败',
      description: error.message,
      variant: 'destructive',
    })
  }
}

// 刷新任务详情
async function refreshTaskDetail() {
  if (!selectedTask.value) return
  try {
    selectedTask.value = await asyncTasksApi.getDetail(selectedTask.value.id)
  } catch (error: any) {
    toast({
      title: '刷新失败',
      description: error.message,
      variant: 'destructive',
    })
  }
}

// 切换详情自动刷新
function toggleDetailAutoRefresh() {
  detailAutoRefresh.value = !detailAutoRefresh.value
  if (detailAutoRefresh.value) {
    startDetailAutoRefresh()
  } else {
    stopDetailAutoRefresh()
  }
}

// 开始详情自动刷新
function startDetailAutoRefresh() {
  if (detailRefreshInterval) return
  // 立即刷新一次
  refreshTaskDetail()
  detailRefreshInterval = setInterval(() => {
    if (selectedTask.value && showDetail.value) {
      refreshTaskDetail()
    }
  }, 5000)
}

// 停止详情自动刷新
function stopDetailAutoRefresh() {
  if (detailRefreshInterval) {
    clearInterval(detailRefreshInterval)
    detailRefreshInterval = null
  }
  detailAutoRefresh.value = false
}

// 关闭详情抽屉
function closeDetail() {
  stopDetailAutoRefresh()
  showDetail.value = false
  selectedTask.value = null
}

// 打开使用记录详情抽屉
async function openUsageRecord(task: AsyncTaskItem) {
  try {
    // 获取任务详情以获得 request_id
    const detail = await asyncTasksApi.getDetail(task.id)
    const requestId = detail.request_metadata?.request_id
    if (requestId) {
      usageRequestId.value = requestId
      usageDetailOpen.value = true
    } else {
      toast({
        title: '无法打开使用记录',
        description: '该任务没有关联的请求ID',
        variant: 'destructive',
      })
    }
  } catch (error: any) {
    toast({
      title: '获取任务信息失败',
      description: error.message,
      variant: 'destructive',
    })
  }
}

// 取消任务
async function cancelTask(task: AsyncTaskItem | AsyncTaskDetail) {
  if (!confirm('确定要取消这个任务吗？')) return
  try {
    await asyncTasksApi.cancel(task.id)
    toast({
      title: '任务已取消',
    })
    fetchTasks()
    fetchStats()
    if (showDetail.value) {
      closeDetail()
    }
  } catch (error: any) {
    toast({
      title: '取消任务失败',
      description: error.message,
      variant: 'destructive',
    })
  }
}

// 状态相关
function getStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'completed':
      return 'default'
    case 'failed':
      return 'destructive'
    case 'cancelled':
      return 'outline'
    default:
      return 'secondary'
  }
}

function getStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending: '待处理',
    submitted: '已提交',
    queued: '排队中',
    processing: '处理中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return labels[status] || status
}

function canCancel(status: string): boolean {
  return ['pending', 'submitted', 'queued', 'processing'].includes(status)
}

// 格式化日期（简短格式，用于表格列表）
function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

// 格式化日期（完整格式，用于详情）
function formatDateFull(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

// 格式化时间（带毫秒，用于时间范围）
function formatTimeWithMs(dateStr: string | null): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  const seconds = date.getSeconds().toString().padStart(2, '0')
  const ms = date.getMilliseconds().toString().padStart(3, '0')
  return `${hours}:${minutes}:${seconds}.${ms}`
}

// 格式化文件大小
function formatFileSize(bytes: number | null): string {
  if (!bytes) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  return `${size.toFixed(unitIndex > 0 ? 2 : 0)} ${units[unitIndex]}`
}

// 获取视频 URL（需要认证的 Google URL 使用代理）
function getVideoUrl(taskId: string, originalUrl: string): string {
  // Google API 链接需要代理
  if (originalUrl.includes('generativelanguage.googleapis.com')) {
    // 从 localStorage 获取 token 作为 query param
    const token = localStorage.getItem('access_token')
    if (token) {
      return `/api/admin/video-tasks/${taskId}/video?token=${encodeURIComponent(token)}`
    }
    return `/api/admin/video-tasks/${taskId}/video`
  }
  return originalUrl
}

// 计算时间差
function calcDuration(startStr: string, endStr: string): string {
  const start = new Date(startStr).getTime()
  const end = new Date(endStr).getTime()
  const diffMs = end - start
  if (diffMs < 1000) return `${diffMs}ms`
  const diffS = diffMs / 1000
  if (diffS < 60) return `${diffS.toFixed(1)}s`
  const mins = Math.floor(diffS / 60)
  const secs = Math.floor(diffS % 60)
  return `${mins}m${secs}s`
}


// 格式化 JSON
function formatJson(obj: any): string {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

// 分页
function goToPage(page: number) {
  currentPage.value = page
  fetchTasks()
}

function handlePageSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  fetchTasks()
}

// 监听筛选条件变化
let filterTimeout: number
watch(filterStatus, () => {
  currentPage.value = 1
  fetchTasks()
})
watch(filterModel, () => {
  clearTimeout(filterTimeout)
  filterTimeout = window.setTimeout(() => {
    currentPage.value = 1
    fetchTasks()
  }, 400)
})

// 检查是否有进行中的任务
const hasProcessingTasks = computed(() => {
  return tasks.value.some(t =>
    ['pending', 'submitted', 'queued', 'processing'].includes(t.status)
  )
})

// 自动刷新逻辑
let autoRefreshInterval: ReturnType<typeof setInterval> | null = null
const AUTO_REFRESH_INTERVAL = 5000 // 5秒

function startAutoRefresh() {
  if (autoRefreshInterval) return
  autoRefreshInterval = setInterval(() => {
    if (hasProcessingTasks.value && !loading.value) {
      fetchTasks()
      fetchStats()
    }
  }, AUTO_REFRESH_INTERVAL)
}

function stopAutoRefresh() {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval)
    autoRefreshInterval = null
  }
}

// 监听是否有进行中的任务，动态启停自动刷新
watch(hasProcessingTasks, (has) => {
  if (has) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}, { immediate: true })

onMounted(() => {
  fetchTasks()
  fetchStats()
})

onUnmounted(() => {
  stopAutoRefresh()
  stopDetailAutoRefresh()
  clearTimeout(filterTimeout)
})
</script>
