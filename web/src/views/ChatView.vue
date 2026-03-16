<template>
  <div class="chat-layout">
    <!-- 左侧会话列表 -->
    <aside class="chat-sidebar">
      <div class="sidebar-header">
        <h2 class="sidebar-title">AI 需求分析</h2>
        <el-dropdown trigger="click" @command="handleNewChatWithMode">
          <el-button type="primary" size="small">
            + 新对话 <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="free">自由对话模式</el-dropdown-item>
              <el-dropdown-item command="agile">敏捷工程模式</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <div class="session-list">
        <div
          v-for="session in chatStore.sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: chatStore.currentSessionId === session.id }"
          @click="handleSwitchSession(session.id)"
        >
          <!-- 会话标题：双击进入编辑模式 -->
          <div v-if="renamingSessionId === session.id" class="session-title-edit" @click.stop>
            <input
              ref="renameInputRef"
              v-model="renameText"
              class="rename-input"
              maxlength="100"
              @keydown.enter="confirmRename(session.id)"
              @keydown.escape="cancelRename"
              @blur="confirmRename(session.id)"
            />
          </div>
          <div
            v-else
            class="session-title"
            @dblclick.stop="startRename(session.id, session.title)"
          >
            {{ session.title || '新对话' }}
          </div>
          <div class="session-meta">
            <span class="session-mode-badge" :class="session.mode" v-if="session.mode === 'agile'">
              敏捷
            </span>
            <span class="session-status" :class="session.status">
              {{ statusLabel(session.status) }}
            </span>
            <div class="session-actions">
              <el-icon
                class="session-action-icon session-edit"
                @click.stop="startRename(session.id, session.title)"
                title="重命名"
              >
                <Edit />
              </el-icon>
              <el-icon
                class="session-action-icon session-delete"
                @click.stop="handleDeleteSession(session.id)"
                title="删除"
              >
                <Delete />
              </el-icon>
            </div>
          </div>
        </div>
        <div v-if="chatStore.sessions.length === 0" class="empty-sessions">
          暂无对话，点击上方按钮开始
        </div>
      </div>
      <!-- 底部信息 -->
      <div class="sidebar-footer">
        <span class="footer-label">AI 需求与详设生成器</span>
      </div>
    </aside>

    <!-- 右侧聊天主区域 -->
    <main class="chat-main">
      <!-- 未选择会话时的欢迎页 -->
      <div v-if="!chatStore.currentSessionId" class="welcome-screen">
        <div class="welcome-content">
          <h1 class="welcome-title">AI 需求与详设生成器</h1>
          <p class="welcome-desc">
            专业的技术产品专家，助力你的想法落地为可开发的逻辑
          </p>
          
          <div class="mode-selector-wrap">
            <div class="mode-card free" @click="handleNewChatWithMode('free')">
              <div class="mode-icon"><Compass /></div>
              <h3 class="mode-name">自由对话模式</h3>
              <p class="mode-intro">头脑风暴，零散记录，随时捕捉灵感，AI 实时辅助补充。</p>
              <el-button type="primary" link>点击进入 ></el-button>
            </div>
            
            <div class="mode-card agile" @click="handleNewChatWithMode('agile')">
              <div class="mode-icon"><Checked /></div>
              <h3 class="mode-name">敏捷工程模式</h3>
              <p class="mode-intro">严格遵循软件工程规范，从用户故事到数据库设计，步步为营。</p>
              <el-button type="success" link>点击进入 ></el-button>
            </div>
          </div>

          <div class="welcome-examples">
            <p class="examples-title">试试这些：</p>
            <div class="example-chips">
              <span
                v-for="example in quickExamples"
                :key="example"
                class="example-chip"
                @click="handleQuickStart(example)"
              >
                {{ example }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 聊天消息区域 -->
      <div v-else class="chat-container">
        <!-- 敏捷模式进度轴 -->
        <div v-if="chatStore.currentSession?.mode === 'agile'" class="agile-stepper">
          <div
            v-for="(stage, idx) in AGILE_STAGES"
            :key="stage.id"
            class="stage-node"
            :class="[getStageStatus(idx), { active: chatStore.currentSession?.current_stage === stage.id }]"
            @click="handleStageClick(stage.id)"
          >
            <div class="stage-icon-wrap">
              <el-icon><component :is="stage.icon" /></el-icon>
              <div class="stage-check" v-if="getStageStatus(idx) === 'success'">
                <el-icon><CircleCheckFilled /></el-icon>
              </div>
            </div>
            <span class="stage-label">{{ stage.label }}</span>
            <div class="stage-line" v-if="idx < AGILE_STAGES.length - 1"></div>
          </div>
        </div>

        <!-- 敏捷模式：环节大纲面板（可折叠，支持查看详情与生成附件） -->
        <div v-if="chatStore.currentSession?.mode === 'agile' && chatStore.stageSummaries.length > 0" class="stage-outline-panel">
          <div class="stage-outline-header" @click="stageOutlineCollapsed = !stageOutlineCollapsed">
            <el-icon class="stage-outline-toggle" :class="{ collapsed: stageOutlineCollapsed }">
              <ArrowDown />
            </el-icon>
            <span class="stage-outline-title">环节大纲</span>
            <span class="stage-outline-count">{{ chatStore.stageSummaries.length }} 个环节已完成</span>
          </div>
          <div v-show="!stageOutlineCollapsed" class="stage-outline-body">
            <div
              v-for="s in chatStore.stageSummaries"
              :key="s.stage"
              class="stage-outline-item"
            >
              <div class="stage-outline-item-header">
                <el-tag size="small" type="success">{{ s.label }}</el-tag>
                <span class="stage-outline-item-title">{{ s.title }}</span>
                <el-button
                  link
                  type="primary"
                  size="small"
                  @click="toggleStageDetail(s.stage)"
                >
                  {{ expandedStageId === s.stage ? '收起' : '查看详情' }}
                </el-button>
                <div class="stage-outline-export">
                  <el-dropdown trigger="click" @command="(fmt: string) => handleExportStage(s.stage, fmt)">
                    <el-button size="small" type="primary" plain>
                      生成附件 <el-icon><ArrowDown /></el-icon>
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="docx">Word</el-dropdown-item>
                        <el-dropdown-item command="pdf">PDF</el-dropdown-item>
                        <el-dropdown-item command="pptx">PPT</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
              </div>
              <div v-show="expandedStageId === s.stage" class="stage-outline-item-body markdown-body" v-html="renderMarkdown(s.content)"></div>
            </div>
          </div>
        </div>

        <div class="messages-area" ref="messagesArea">
          <div
            v-for="msg in chatStore.messages"
            :key="msg.id"
            class="message-row"
            :class="msg.role"
          >
            <!-- 用户消息 -->
            <div v-if="msg.role === 'user' && msg.msg_type === 'file'" class="message-bubble user-bubble">
              <div class="file-bubble">
                <div class="file-bubble-icon">
                  <el-icon :size="24"><Document /></el-icon>
                </div>
                <div class="file-bubble-info">
                  <div class="file-bubble-name">{{ (msg.metadata as any)?.filename || '文件' }}</div>
                  <div class="file-bubble-meta">
                    <span>{{ (msg.metadata as any)?.file_type || '文件' }}</span>
                    <span class="file-meta-sep">·</span>
                    <span>{{ formatFileSize((msg.metadata as any)?.file_size) }}</span>
                    <span class="file-meta-sep">·</span>
                    <span>{{ (msg.metadata as any)?.char_count?.toLocaleString() }} 字符</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else-if="msg.role === 'user'" class="message-bubble user-bubble">
              <div class="bubble-content">{{ msg.content }}</div>
            </div>

            <!-- 助手文本消息 -->
            <div
              v-else-if="msg.role === 'assistant' && msg.msg_type === 'text'"
              class="message-bubble assistant-bubble"
              :class="{ 'select-mode-msg': chatStore.selectMode, 'msg-selected': chatStore.selectMode && chatStore.selectedMessageIds.has(msg.id) }"
            >
              <el-checkbox
                v-if="chatStore.selectMode && msg.content"
                class="msg-select-checkbox"
                :model-value="chatStore.selectedMessageIds.has(msg.id)"
                @change="chatStore.toggleMessageSelection(msg.id)"
              />
              <div class="bubble-avatar">AI</div>
              <div class="bubble-content markdown-body" v-html="renderMarkdown(msg.content)"></div>
            </div>

            <!-- 大纲消息 -->
            <div
              v-else-if="msg.msg_type === 'outline'"
              class="message-bubble assistant-bubble"
            >
              <div class="bubble-avatar">AI</div>
              <div class="outline-card">
                <h3 class="outline-title">
                  {{ (msg.metadata as any)?.project_name || '需求大纲' }}
                </h3>
                <div class="outline-info">
                  <el-tag effect="plain" size="small">
                    {{ (msg.metadata as any)?.domain || '未分类' }}
                  </el-tag>
                  <el-tag effect="plain" size="small" type="info">
                    {{ (msg.metadata as any)?.complexity || '中等' }}
                  </el-tag>
                </div>

                <div class="outline-section" v-if="(msg.metadata as any)?.target_users?.length">
                  <span class="outline-label">目标用户：</span>
                  <el-tag
                    v-for="u in (msg.metadata as any).target_users"
                    :key="u"
                    size="small"
                    class="outline-tag"
                  >{{ u }}</el-tag>
                </div>

                <div class="outline-section" v-if="(msg.metadata as any)?.core_modules?.length">
                  <span class="outline-label">核心模块：</span>
                  <div class="module-list">
                    <div
                      v-for="m in (msg.metadata as any).core_modules"
                      :key="typeof m === 'string' ? m : m.name"
                      class="module-item"
                    >
                      <strong>{{ typeof m === 'string' ? m : m.name }}</strong>
                      <span v-if="typeof m !== 'string' && m.description"> — {{ m.description }}</span>
                    </div>
                  </div>
                </div>

                <div class="outline-section" v-if="(msg.metadata as any)?.feature_list?.length">
                  <span class="outline-label">功能点列表 ({{ (msg.metadata as any).feature_list.length }})：</span>
                  <div class="feature-list">
                    <div
                      v-for="(f, idx) in (msg.metadata as any).feature_list"
                      :key="idx"
                      class="feature-item"
                    >
                      {{ idx + 1 }}. {{ f }}
                    </div>
                  </div>
                </div>

                <div class="outline-actions" v-if="chatStore.currentSession?.status === 'active'">
                  <div class="doc-config-title">请选择需要生成的文档及导出格式：</div>
                  
                  <div class="doc-config-list">
                    <!-- 需求大纲 -->
                    <div class="doc-config-card" :class="{ 'is-active': docConfigs.outline.selected }">
                      <div class="doc-config-header">
                        <el-checkbox v-model="docConfigs.outline.selected" class="doc-config-checkbox">
                          <span class="doc-config-label">需求大纲</span>
                        </el-checkbox>
                      </div>
                      <div class="doc-config-body" v-if="docConfigs.outline.selected">
                        <el-checkbox-group v-model="docConfigs.outline.formats" size="small">
                          <el-checkbox-button label="pdf">PDF</el-checkbox-button>
                          <el-checkbox-button label="docx">Word</el-checkbox-button>
                          <el-checkbox-button label="pptx">PPT</el-checkbox-button>
                        </el-checkbox-group>
                      </div>
                    </div>

                    <!-- 需求详细设计 -->
                    <div class="doc-config-card" :class="{ 'is-active': docConfigs.detail.selected }">
                      <div class="doc-config-header">
                        <el-checkbox v-model="docConfigs.detail.selected" class="doc-config-checkbox">
                          <span class="doc-config-label">需求详细设计</span>
                        </el-checkbox>
                      </div>
                      <div class="doc-config-body" v-if="docConfigs.detail.selected">
                        <el-checkbox-group v-model="docConfigs.detail.formats" size="small">
                          <el-checkbox-button label="pdf">PDF</el-checkbox-button>
                          <el-checkbox-button label="docx">Word</el-checkbox-button>
                          <el-checkbox-button label="pptx">PPT</el-checkbox-button>
                        </el-checkbox-group>
                      </div>
                    </div>

                    <!-- 需求立项报告 -->
                    <div class="doc-config-card" :class="{ 'is-active': docConfigs.proposal_ppt.selected }">
                      <div class="doc-config-header">
                        <el-checkbox v-model="docConfigs.proposal_ppt.selected" class="doc-config-checkbox">
                          <span class="doc-config-label">需求立项报告 (PPT)</span>
                        </el-checkbox>
                      </div>
                      <div class="doc-config-body" v-if="docConfigs.proposal_ppt.selected">
                        <el-checkbox-group v-model="docConfigs.proposal_ppt.formats" size="small">
                          <el-checkbox-button label="pdf">PDF</el-checkbox-button>
                          <el-checkbox-button label="docx">Word</el-checkbox-button>
                          <el-checkbox-button label="pptx">PPT</el-checkbox-button>
                        </el-checkbox-group>
                      </div>
                    </div>
                  </div>

                  <div class="outline-btns">
                    <el-button @click="chatStore.sendMessage('我想调整一下需求大纲')">
                      返回修改
                    </el-button>
                    <el-button
                      type="primary"
                      :loading="chatStore.confirming"
                      :disabled="!docConfigs.outline.selected && !docConfigs.detail.selected && !docConfigs.proposal_ppt.selected"
                      @click="handleConfirm"
                    >
                      确认，开始生成
                    </el-button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 进度消息 -->
            <div
              v-else-if="msg.msg_type === 'progress'"
              class="message-bubble system-bubble"
            >
              <div class="progress-msg">
                <el-icon v-if="!(msg.metadata as any)?.done"><Loading /></el-icon>
                <el-icon v-else class="done-icon"><CircleCheckFilled /></el-icon>
                <span>{{ msg.content }}</span>
              </div>
            </div>

            <!-- 产出物消息 -->
            <div
              v-else-if="msg.msg_type === 'artifact'"
              class="message-bubble assistant-bubble artifact-bubble"
            >
              <div class="bubble-avatar">AI</div>
              <div class="artifact-card">
                <div class="artifact-header">
                  <el-icon><Document /></el-icon>
                  <span class="artifact-title">{{ (msg.metadata as any)?.display_name || '产出物' }}</span>
                  <el-tag size="small" effect="plain" type="info">
                    {{ (msg.metadata as any)?.output_type || 'markdown' }}
                  </el-tag>
                </div>
                <!-- 导出文件（PDF/Word/PPT）：仅显示下载按钮 -->
                <div v-if="isExportArtifact(msg)" class="artifact-export">
                  <p class="export-desc">{{ exportFormatLabel((msg.metadata as any)?.export_format) }} 已生成，点击下方按钮下载。</p>
                  <el-button type="primary" size="default" @click="downloadExportFile(msg)">
                    下载 {{ exportFormatLabel((msg.metadata as any)?.export_format) }}
                  </el-button>
                </div>
                <template v-else>
                  <div
                    class="artifact-content markdown-body"
                    v-html="renderMarkdown(msg.content)"
                    ref="artifactRefs"
                  ></div>
                  <div class="artifact-footer">
                    <el-button size="small" @click="copyContent(msg.content)">
                      复制内容
                    </el-button>
                    <el-button size="small" type="primary" @click="downloadArtifact(msg)">
                      下载文件
                    </el-button>
                  </div>
                </template>
              </div>
            </div>

            <!-- 系统消息 -->
            <div
              v-else-if="msg.role === 'system' && msg.msg_type === 'text'"
              class="message-bubble system-bubble"
            >
              <span>{{ msg.content }}</span>
            </div>

            <!-- 敏捷里程碑消息 -->
            <div
              v-else-if="msg.msg_type === 'milestone'"
              class="message-bubble assistant-bubble milestone-bubble"
            >
              <div class="bubble-avatar">成果</div>
              <div class="milestone-card">
                <div class="milestone-header">
                  <el-icon><CircleCheckFilled /></el-icon>
                  <span class="milestone-title">{{ (msg.metadata as any)?.title || '阶段性成果' }}</span>
                  <el-tag size="small" type="success" effect="dark">
                    {{ AGILE_STAGES.find(s => s.id === (msg.metadata as any)?.stage)?.label || '已完成' }}
                  </el-tag>
                </div>
                <div class="milestone-body markdown-body" v-html="renderMarkdown(msg.content)"></div>
                <div class="milestone-footer">
                  <span class="milestone-tip">此内容已纳入项目上下文，你可以基于此继续完善</span>
                  <div class="milestone-actions">
                    <el-button size="small" @click="copyContent(msg.content)">复制内容</el-button>
                    <el-dropdown v-if="(msg.metadata as any)?.stage" trigger="click" @command="(fmt: string) => handleExportStage((msg.metadata as any).stage, fmt)">
                      <el-button size="small" type="primary" plain>生成附件</el-button>
                      <template #dropdown>
                        <el-dropdown-menu>
                          <el-dropdown-item command="docx">Word</el-dropdown-item>
                          <el-dropdown-item command="pdf">PDF</el-dropdown-item>
                          <el-dropdown-item command="pptx">PPT</el-dropdown-item>
                        </el-dropdown-menu>
                      </template>
                    </el-dropdown>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 流式打字指示器 -->
          <div v-if="chatStore.streaming" class="typing-indicator">
            <div class="bubble-avatar">AI</div>
            <div class="typing-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>

        <!-- 敏捷模式：环节完成确认卡片（AI 询问是否进入下一环节时显示） -->
        <div v-if="chatStore.stageReady && chatStore.currentSession?.mode === 'agile'" class="stage-confirm-bar">
          <div class="stage-confirm-content">
            <el-icon class="stage-confirm-icon"><CircleCheckFilled /></el-icon>
            <div class="stage-confirm-text">
              <span class="stage-confirm-title">本环节内容已足够</span>
              <span class="stage-confirm-desc">是否进入下一环节？如需生成本环节附件，可点击下方按钮。</span>
            </div>
          </div>
          <div class="stage-confirm-actions">
            <el-button
              v-if="!isLastStage"
              type="primary"
              @click="handleAdvanceStage()"
            >
              进入下一环节
            </el-button>
            <el-button plain @click="chatStore.clearStageReady()">继续完善</el-button>
            <el-dropdown v-if="chatStore.stageReady" trigger="click" @command="(fmt: string) => handleExportStage(chatStore.stageReady!.stage, fmt)">
              <el-button type="success" plain>生成本环节附件</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="docx">Word</el-dropdown-item>
                  <el-dropdown-item command="pdf">PDF</el-dropdown-item>
                  <el-dropdown-item command="pptx">PPT</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>

        <!-- 底部：消息选择导出栏（选择模式下替代输入区域） -->
        <div v-if="chatStore.selectMode" class="export-select-bar">
          <div class="export-select-left">
            <div class="export-select-header">
              <el-icon class="export-icon"><Document /></el-icon>
              <span class="export-select-title">选择要导出的消息</span>
              <span class="export-select-count" v-if="chatStore.selectedMessageIds.size > 0">
                已选 {{ chatStore.selectedMessageIds.size }} 条
              </span>
            </div>
            <div class="export-select-controls">
              <el-button link type="primary" @click="chatStore.selectAllMessages()">全选</el-button>
              <el-divider direction="vertical" />
              <el-button link type="info" @click="chatStore.deselectAllMessages()">全不选</el-button>
            </div>
          </div>
          
          <div class="export-select-right">
            <div class="export-format-wrapper">
              <span class="format-label">格式：</span>
              <el-radio-group v-model="selectedExportFormat" size="default" class="export-format-group">
                <el-radio-button value="docx">Word</el-radio-button>
                <el-radio-button value="pdf">PDF</el-radio-button>
                <el-radio-button value="pptx">PPT</el-radio-button>
              </el-radio-group>
            </div>
            <div class="export-select-actions">
              <el-button size="default" plain @click="chatStore.exitSelectMode()">取消</el-button>
              <el-button
                type="primary"
                size="default"
                :loading="chatStore.exporting"
                :disabled="chatStore.selectedMessageIds.size === 0"
                @click="handleExportSelected"
              >
                生成文档
              </el-button>
            </div>
          </div>
        </div>

        <!-- 底部输入区域 -->
        <div v-else class="input-area">
          <!-- 文件待上传预览栏 -->
          <div v-if="pendingFile" class="file-pending-bar">
            <div class="file-pending-info">
              <el-icon :size="18" color="#409eff"><Document /></el-icon>
              <span class="file-pending-name">{{ pendingFile.name }}</span>
              <span class="file-pending-size">{{ formatFileSize(pendingFile.size) }}</span>
            </div>
            <el-button
              :icon="Close"
              circle
              size="small"
              class="file-pending-close"
              @click="clearPendingFile"
            />
          </div>
          <div class="input-wrapper">
            <!-- 隐藏的文件输入 -->
            <input
              ref="fileInputRef"
              type="file"
              class="hidden-file-input"
              accept=".txt,.md,.csv,.json,.xml,.yaml,.yml,.docx,.pdf,.html,.py,.java,.js,.ts,.sql,.log"
              @change="handleFileSelected"
            />
            <!-- 文件上传按钮 -->
            <el-button
              circle
              class="upload-btn"
              :disabled="chatStore.streaming || chatStore.isGenerating || chatStore.uploading"
              :loading="chatStore.uploading"
              @click="triggerFileInput"
            >
              <el-icon v-if="!chatStore.uploading"><Paperclip /></el-icon>
            </el-button>
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="1"
              :autosize="{ minRows: 1, maxRows: 6 }"
              :placeholder="pendingFile ? '输入对文件的说明或指令（如：帮我补充完善）...' : '描述你想做的产品，或回答 AI 的问题...'"
              @keydown.enter.exact.prevent="handleSend"
              :disabled="chatStore.streaming || chatStore.isGenerating"
            />
            <!-- 发送 / 停止按钮 -->
            <el-button
              v-if="!chatStore.streaming"
              type="primary"
              circle
              class="send-btn"
              :disabled="!inputText.trim() && !pendingFile"
              @click="handleSend"
            >
              <el-icon><Promotion /></el-icon>
            </el-button>
            <el-button
              v-else
              type="danger"
              circle
              class="send-btn"
              @click="handleStop"
            >
              <el-icon><VideoPause /></el-icon>
            </el-button>
          </div>
          <div class="input-hint">
            {{ chatStore.streaming ? '点击红色按钮停止生成' : chatStore.uploading ? '文件上传中...' : '按 Enter 发送，Shift+Enter 换行 | 点击回形针上传文件' }}
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
/**
 * ChatView — 全屏对话式需求分析界面
 * 左侧会话列表 + 右侧 ChatGPT 风格的聊天主区域。
 */
import { ref, computed, onMounted, nextTick, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Delete, Loading, CircleCheckFilled, Document, Promotion, VideoPause,
  UploadFilled, Close, Paperclip, Compass, Checked, Monitor, Cpu, DataLine, List,
  ArrowDown, Edit, Check,
} from '@element-plus/icons-vue'
import mermaid from 'mermaid'
import { useChatStore } from '@/stores/chat'
import type { ChatMessage } from '@/stores/chat'

const route = useRoute()
const router = useRouter()
const chatStore = useChatStore()
const inputText = ref('')
const messagesArea = ref<HTMLElement | null>(null)

// 每个文档类型的配置状态
const docConfigs = ref({
  outline: { selected: false, formats: ['docx'] },
  detail: { selected: true, formats: ['docx'] },
  proposal_ppt: { selected: false, formats: ['pptx'] },
})

// 当复选框被勾选时，如果没有格式被选中，恢复默认格式
watch(() => docConfigs.value.outline.selected, (val) => {
  if (val && docConfigs.value.outline.formats.length === 0) docConfigs.value.outline.formats = ['docx']
})
watch(() => docConfigs.value.detail.selected, (val) => {
  if (val && docConfigs.value.detail.formats.length === 0) docConfigs.value.detail.formats = ['docx']
})
watch(() => docConfigs.value.proposal_ppt.selected, (val) => {
  if (val && docConfigs.value.proposal_ppt.formats.length === 0) docConfigs.value.proposal_ppt.formats = ['pptx']
})

// 消息选择模式下的导出格式
const selectedExportFormat = ref('docx')

// 文件上传相关状态
const fileInputRef = ref<HTMLInputElement | null>(null)
const pendingFile = ref<File | null>(null)

// 会话重命名相关状态
const renamingSessionId = ref<string | null>(null)
const renameText = ref('')
const renameInputRef = ref<HTMLInputElement | null>(null)

// 敏捷模式：环节大纲面板折叠、详情展开
const stageOutlineCollapsed = ref(false)
const expandedStageId = ref<string | null>(null)

/** 敏捷工作流阶段定义（7 个节点，覆盖从想法到交付的完整链路） */
const AGILE_STAGES = [
  { id: 'discovery', label: '需求洞察', icon: Compass },
  { id: 'business_case', label: '立项论证', icon: DataLine },
  { id: 'product_backlog', label: '产品规划', icon: List },
  { id: 'architecture', label: '架构设计', icon: Cpu },
  { id: 'ux_prototype', label: '交互原型', icon: Monitor },
  { id: 'delivery_plan', label: '交付计划', icon: Checked },
  { id: 'review', label: '评审输出', icon: Document },
]

/** 计算当前阶段的索引 */
const currentStageIndex = computed(() => {
  const stageId = chatStore.currentSession?.current_stage
  return AGILE_STAGES.findIndex(s => s.id === stageId)
})

/** 是否为最后一环节（评审输出） */
const isLastStage = computed(() => {
  return currentStageIndex.value >= 0 && currentStageIndex.value >= AGILE_STAGES.length - 1
})

/** 获取阶段状态 */
const getStageStatus = (index: number) => {
  if (index < currentStageIndex.value) return 'success'
  if (index === currentStageIndex.value) return 'process'
  return 'wait'
}

/** 手动点击进度轴切换阶段 */
const handleStageClick = async (stageId: string) => {
  if (!chatStore.currentSessionId) return
  try {
    await ElMessageBox.confirm(`确定要切换到"${AGILE_STAGES.find(s => s.id === stageId)?.label}"阶段吗？`, '切换阶段', {
      type: 'info'
    })
    await chatStore.updateStage(chatStore.currentSessionId, stageId)
    ElMessage.success('阶段已切换')
  } catch { /* 取消 */ }
}

const quickExamples = [
  '帮我做一个保险公司的智能培训系统',
  '设计一个 CRM 客户管理系统',
  '搭建一个在线教育平台',
  '做一个电商后台管理系统',
]

mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
  suppressErrorRendering: true,
  flowchart: { useMaxWidth: true, htmlLabels: true },
})

/** 清理 Mermaid 渲染失败时残留在 body 中的错误元素 */
function cleanupMermaidErrors(renderId: string) {
  const orphan = document.getElementById(renderId)
  if (orphan) orphan.remove()
  const dOrphan = document.getElementById('d' + renderId)
  if (dOrphan) dOrphan.remove()
  document.querySelectorAll('[id^="mermaid-"] [id*="err"]').forEach(el => {
    const parent = el.closest('[id^="dmermaid-"]')
    if (parent && !parent.closest('.mermaid-block')) parent.remove()
  })
}

/** 构建 Mermaid 渲染失败时的降级提示 HTML */
function buildMermaidFallback(code: string): string {
  return `<div class="mermaid-fallback">
    <div class="mermaid-fallback-msg">
      图表语法暂无法自动渲染，可复制下方代码到
      <a href="https://mermaid.live" target="_blank" rel="noopener">Mermaid Live</a> 在线查看
    </div>
    <pre class="mermaid-fallback-code">${escapeHtml(code)}</pre>
  </div>`
}

/** 渲染页面中所有未渲染的 Mermaid 代码块；失败时显示源码与友好提示 */
async function renderMermaidBlocks() {
  await nextTick()
  const blocks = document.querySelectorAll('.mermaid-source:not(.mermaid-rendered)')
  for (let i = 0; i < blocks.length; i++) {
    const el = blocks[i] as HTMLElement
    const code = el.textContent?.trim() || ''
    if (!code) continue
    el.classList.add('mermaid-rendered')
    const container = el.parentElement
    if (!container) continue

    const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 9)}-${i}`

    // 先用 parse 验证语法，避免 render 在 DOM 中注入错误元素
    let syntaxOk = false
    try {
      await mermaid.parse(code)
      syntaxOk = true
    } catch {
      syntaxOk = false
    }

    if (!syntaxOk) {
      container.innerHTML = buildMermaidFallback(code)
      container.classList.add('mermaid-rendered-container')
      continue
    }

    try {
      const { svg } = await mermaid.render(id, code)
      container.innerHTML = svg
      container.classList.add('mermaid-rendered-container')
    } catch {
      cleanupMermaidErrors(id)
      container.innerHTML = buildMermaidFallback(code)
      container.classList.add('mermaid-rendered-container')
    }
  }
}

function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

/** 清理 body 中所有 Mermaid 渲染残留的孤立错误元素 */
function cleanupAllMermaidOrphans() {
  document.querySelectorAll('body > [id^="dmermaid-"], body > svg[id^="mermaid-"]').forEach(el => el.remove())
  document.querySelectorAll('body > #d[id], body > [data-mermaid-temp]').forEach(el => el.remove())
}

onMounted(async () => {
  cleanupAllMermaidOrphans()
  await chatStore.loadSessions()
  const sessionId = route.params.sessionId as string
  if (sessionId) {
    await chatStore.switchSession(sessionId)
  }
})

onUnmounted(() => {
  chatStore.stopPolling()
  cleanupAllMermaidOrphans()
})

/** 滚动到消息底部 */
function scrollToBottom() {
  nextTick(() => {
    if (messagesArea.value) {
      messagesArea.value.scrollTop = messagesArea.value.scrollHeight
    }
  })
}

watch(() => chatStore.messages.length, () => {
  scrollToBottom()
  renderMermaidBlocks()
})
watch(() => chatStore.streaming, scrollToBottom)

/** 简单的 Markdown 渲染（将关键标记转为 HTML） */
function renderMarkdown(text: string): string {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Mermaid 代码块：保留原始内容，由后续逻辑渲染
  html = html.replace(
    /```mermaid\n([\s\S]*?)```/g,
    '<div class="mermaid-block"><pre class="mermaid-source">$1</pre></div>'
  )
  // 普通代码块
  html = html.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    '<pre class="code-block"><code>$2</code></pre>'
  )
  // 行内代码
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  // 表格
  html = renderTables(html)
  // 标题
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  // 粗体和斜体
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  // 列表
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
  // 分割线
  html = html.replace(/^---$/gm, '<hr/>')
  // 换行
  html = html.replace(/\n/g, '<br/>')
  // 修复列表包裹
  html = html.replace(/(<li>.*?<\/li>(<br\/>)?)+/g, (match) => {
    return '<ul>' + match.replace(/<br\/>/g, '') + '</ul>'
  })
  return html
}

/** Markdown 表格渲染 */
function renderTables(text: string): string {
  const tableRegex = /(\|.+\|[\r\n]+\|[-| :]+\|[\r\n]+((\|.+\|[\r\n]*)+))/g
  return text.replace(tableRegex, (match) => {
    const rows = match.trim().split('\n').filter(r => r.trim())
    if (rows.length < 2) return match

    const headerCells = rows[0].split('|').filter(c => c.trim())
    const dataRows = rows.slice(2)

    let table = '<table class="md-table"><thead><tr>'
    for (const cell of headerCells) {
      table += `<th>${cell.trim()}</th>`
    }
    table += '</tr></thead><tbody>'
    for (const row of dataRows) {
      const cells = row.split('|').filter(c => c.trim())
      table += '<tr>'
      for (const cell of cells) {
        table += `<td>${cell.trim()}</td>`
      }
      table += '</tr>'
    }
    table += '</tbody></table>'
    return table
  })
}

/** 会话状态中文标签 */
function statusLabel(status: string): string {
  const map: Record<string, string> = {
    active: '对话中',
    confirmed: '已确认',
    generating: '生成中',
    completed: '已完成',
  }
  return map[status] || status
}

/** 创建新对话 */
async function handleNewChat() {
  await handleNewChatWithMode('free')
}

/** 创建指定模式的新对话 */
async function handleNewChatWithMode(mode: string) {
  const sessionId = await chatStore.createSession('', mode)
  if (sessionId) {
    await chatStore.switchSession(sessionId)
    router.replace({ name: 'chatSession', params: { sessionId } })
  }
}

/** 快捷示例：创建新对话并发送 */
async function handleQuickStart(example: string) {
  const sessionId = await chatStore.createSession('', 'free')
  if (sessionId) {
    await chatStore.switchSession(sessionId)
    router.replace({ name: 'chatSession', params: { sessionId } })
    await nextTick()
    await chatStore.sendMessage(example)
  }
}

/** 切换会话 */
async function handleSwitchSession(sessionId: string) {
  cleanupAllMermaidOrphans()
  await chatStore.switchSession(sessionId)
  router.replace({ name: 'chatSession', params: { sessionId } })
  // 如果正在生成中，恢复轮询
  if (chatStore.currentSession?.status === 'generating') {
    chatStore.startPolling()
  }
}

/** 删除会话 */
async function handleDeleteSession(sessionId: string) {
  try {
    await ElMessageBox.confirm('确定删除这个对话？', '删除确认', {
      type: 'warning',
    })
    await chatStore.deleteSession(sessionId)
  } catch { /* 用户取消 */ }
}

/** 进入重命名模式 */
function startRename(sessionId: string, currentTitle: string) {
  renamingSessionId.value = sessionId
  renameText.value = currentTitle || ''
  nextTick(() => {
    const input = renameInputRef.value
    if (input) {
      if (Array.isArray(input)) {
        (input[0] as HTMLInputElement)?.focus()
      } else {
        input.focus()
      }
    }
  })
}

/** 确认重命名 */
async function confirmRename(sessionId: string) {
  const newTitle = renameText.value.trim()
  if (!newTitle) {
    cancelRename()
    return
  }
  const ok = await chatStore.renameSession(sessionId, newTitle)
  if (ok) {
    ElMessage.success('已重命名')
  }
  renamingSessionId.value = null
  renameText.value = ''
}

/** 取消重命名 */
function cancelRename() {
  renamingSessionId.value = null
  renameText.value = ''
}

/** 切换环节详情展开/收起 */
function toggleStageDetail(stageId: string) {
  expandedStageId.value = expandedStageId.value === stageId ? null : stageId
}

/** 按环节生成附件 */
async function handleExportStage(stageId: string, format: string) {
  if (!chatStore.currentSessionId) return
  const ok = await chatStore.exportStage(chatStore.currentSessionId, stageId, format)
  if (ok) {
    ElMessage.success(`已启动导出，请稍候...`)
  } else {
    ElMessage.error('导出失败，请重试')
  }
}

/** 用户确认进入下一环节 */
async function handleAdvanceStage() {
  if (!chatStore.currentSessionId) return
  const ok = await chatStore.advanceStage(chatStore.currentSessionId)
  if (ok) {
    ElMessage.success('已进入下一环节')
  } else {
    ElMessage.error('切换失败，可能已是最后一环节')
  }
}

/** 发送消息（支持纯文本或文件 + 文本混合发送） */
async function handleSend() {
  const text = inputText.value.trim()
  const file = pendingFile.value

  if (!text && !file) return
  if (chatStore.streaming) return

  inputText.value = ''

  if (file) {
    pendingFile.value = null
    // 上传文件时不附带文字（文字单独通过 sendMessage 发送，避免重复保存）
    const result = await chatStore.uploadFile(file)
    if (!result) {
      ElMessage.error('文件上传失败，请重试')
      return
    }
    ElMessage.success(`文件"${result.filename}"已上传`)

    // 上传完成后发送用户指令给 LLM（文件内容已在对话上下文中）
    const instruction = text || '请帮我分析和完善这个文件的内容'
    await chatStore.sendMessage(instruction)
    return
  }

  await chatStore.sendMessage(text)
}

/** 停止当前对话生成 */
function handleStop() {
  chatStore.stopStreaming()
  ElMessage.info('已停止生成')
}

/** 导出用户选中的消息 */
async function handleExportSelected() {
  const count = chatStore.selectedMessageIds.size
  if (count === 0) {
    ElMessage.warning('请至少选择一条消息')
    return
  }
  const ok = await chatStore.exportSelectedMessages(selectedExportFormat.value)
  if (ok) {
    ElMessage.success('文档导出已启动，请稍候...')
  } else {
    ElMessage.error('导出失败，请重试')
  }
}

/** 触发隐藏的文件输入元素 */
function triggerFileInput() {
  fileInputRef.value?.click()
}

/** 用户选择文件后的处理 */
function handleFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) {
    pendingFile.value = file
  }
  input.value = ''
}

/** 清除待上传的文件 */
function clearPendingFile() {
  pendingFile.value = null
}

/** 格式化文件大小为易读字符串 */
function formatFileSize(bytes: number | undefined): string {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** 确认大纲，传入按文档类型配置的导出格式 */
async function handleConfirm() {
  const configs: Record<string, string[]> = {}
  const typeLabels: Record<string, string> = {
    outline: '需求大纲',
    detail: '需求详细设计',
    proposal_ppt: '需求立项报告',
  }
  const formatLabels: Record<string, string> = { pdf: 'PDF', docx: 'Word', pptx: 'PPT' }
  const selectedLabels: string[] = []

  for (const [key, config] of Object.entries(docConfigs.value)) {
    if (config.selected) {
      configs[key] = config.formats
      const fmtStr = config.formats.length > 0
        ? `(${config.formats.map(f => formatLabels[f] || f).join('/')})`
        : '(不导出)'
      selectedLabels.push(`${typeLabels[key]}${fmtStr}`)
    }
  }

  if (Object.keys(configs).length === 0) {
    ElMessage.warning('请至少选择一种文档类型')
    return
  }

  try {
    await ElMessageBox.confirm(
      `将生成以下内容：\n\n${selectedLabels.join('\n')}\n\n是否继续？`,
      '确认生成',
      { type: 'info', confirmButtonText: '开始生成', cancelButtonText: '再想想' },
    )
    const ok = await chatStore.confirmOutline(configs)
    if (ok) {
      ElMessage.success('文档生成已启动，请稍候...')
    } else {
      ElMessage.error('启动失败，请重试')
    }
  } catch { /* 用户取消 */ }
}

/** 复制内容到剪贴板 */
async function copyContent(content: string) {
  try {
    await navigator.clipboard.writeText(content)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败')
  }
}

/** 是否为导出文件类产出物（PDF/Word/PPT） */
function isExportArtifact(msg: ChatMessage): boolean {
  const meta = msg.metadata as Record<string, unknown> | undefined
  const fmt = meta?.export_format as string | undefined
  const filename = meta?.filename as string | undefined
  return (fmt === 'pdf' || fmt === 'docx' || fmt === 'pptx') && !!filename
}

/** 导出格式中文标签 */
function exportFormatLabel(fmt: string): string {
  const map: Record<string, string> = { pdf: 'PDF', docx: 'Word', pptx: 'PPT' }
  return map[fmt] || fmt
}

/** 导出文件下载地址（会话内 PDF/Word/PPT） */
function exportFileUrl(msg: ChatMessage): string {
  const sid = chatStore.currentSessionId
  const filename = (msg.metadata as Record<string, unknown>)?.filename as string
  if (!sid || !filename) return '#'
  return `/api/chat/sessions/${sid}/files/${encodeURIComponent(filename)}`
}

/** 编程式下载导出文件，避免 target="_blank" 被浏览器拦截 */
async function downloadExportFile(msg: ChatMessage) {
  const url = exportFileUrl(msg)
  if (url === '#') {
    ElMessage.error('下载地址无效')
    return
  }
  const filename = (msg.metadata as Record<string, unknown>)?.filename as string || 'download'
  try {
    const resp = await fetch(url)
    if (!resp.ok) {
      const text = await resp.text()
      ElMessage.error(`下载失败：${text}`)
      return
    }
    const blob = await resp.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(blobUrl)
  } catch (err) {
    console.error('下载失败:', err)
    ElMessage.error('下载失败，请重试')
  }
}

/** 下载产出物为文件 */
function downloadArtifact(msg: ChatMessage) {
  const meta = msg.metadata as Record<string, unknown> | undefined
  const skillName = (meta?.skill_name as string) || 'document'
  const outputType = (meta?.output_type as string) || 'markdown'
  const ext = outputType === 'yaml' ? 'yaml' : 'md'
  const filename = `${skillName}.${ext}`

  const blob = new Blob([msg.content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.chat-layout {
  display: flex;
  height: 100vh;
  background: #f8fafc;
}

/* ── 左侧会话列表 ────────────────────────── */
.chat-sidebar {
  width: 260px;
  background: #ffffff;
  border-right: 1px solid #e8ecf1;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e8ecf1;
}

.sidebar-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.session-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  transition: background 0.2s;
}

.session-item:hover {
  background: #f0f4ff;
}

.session-item.active {
  background: #e8f0fe;
}

.session-title {
  font-size: 13px;
  color: #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.session-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
}

.session-status {
  font-size: 11px;
  color: #999;
}

.session-status.active { color: #409eff; }
.session-status.confirmed { color: #e6a23c; }
.session-status.generating { color: #f56c6c; }
.session-status.completed { color: #67c23a; }

.session-mode-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 500;
}

.session-mode-badge.agile {
  background: #f0f9eb;
  color: #67c23a;
  border: 1px solid #e1f3d8;
}

.session-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

.session-action-icon {
  font-size: 14px;
  color: #ccc;
  cursor: pointer;
  opacity: 0;
  transition: all 0.2s;
}

.session-item:hover .session-action-icon {
  opacity: 1;
}

.session-edit:hover {
  color: #409eff;
}

.session-delete:hover {
  color: #f56c6c;
}

/* ── 重命名输入框 ──────────────────────────── */
.session-title-edit {
  margin-bottom: 4px;
}

.rename-input {
  width: 100%;
  font-size: 13px;
  color: #333;
  padding: 3px 6px;
  border: 1px solid #409eff;
  border-radius: 4px;
  outline: none;
  background: #fff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.15);
}

.empty-sessions {
  text-align: center;
  color: #999;
  font-size: 13px;
  padding: 40px 16px;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid #e8ecf1;
  text-align: center;
}

.footer-label {
  font-size: 11px;
  color: #bbb;
}

/* ── 右侧主区域 ──────────────────────────── */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ── 欢迎页 ──────────────────────────────── */
.welcome-screen {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.welcome-content {
  text-align: center;
  max-width: 560px;
  padding: 40px;
}

.welcome-title {
  font-size: 28px;
  font-weight: 700;
  color: #1a1a2e;
  margin-bottom: 12px;
}

.welcome-desc {
  font-size: 15px;
  color: #666;
  line-height: 1.6;
  margin-bottom: 24px;
}

.welcome-examples {
  margin-top: 32px;
}

.examples-title {
  font-size: 13px;
  color: #999;
  margin-bottom: 12px;
}

.example-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.example-chip {
  padding: 8px 16px;
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 20px;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
}

.example-chip:hover {
  border-color: #409eff;
  color: #409eff;
  background: #f0f7ff;
}

/* ── 聊天容器 ────────────────────────────── */
.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  scroll-behavior: smooth;
}

/* ── 消息气泡 ────────────────────────────── */
.message-row {
  display: flex;
  margin-bottom: 16px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant,
.message-row.system {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 75%;
  display: flex;
  gap: 10px;
}

.user-bubble {
  flex-direction: row-reverse;
}

.user-bubble .bubble-content {
  background: #409eff;
  color: #fff;
  border-radius: 16px 16px 4px 16px;
  padding: 10px 16px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.assistant-bubble .bubble-content {
  background: #fff;
  border: 1px solid #e8ecf1;
  border-radius: 4px 16px 16px 16px;
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.7;
  color: #333;
  word-break: break-word;
}

.system-bubble {
  justify-content: center;
  max-width: 100%;
}

.progress-msg {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #999;
  padding: 6px 16px;
  background: #f5f5f5;
  border-radius: 12px;
}

.done-icon {
  color: #67c23a;
}

/* ── 大纲卡片 ────────────────────────────── */
.outline-card {
  background: #fff;
  border: 1px solid #e0e7ff;
  border-radius: 12px;
  padding: 20px;
  min-width: 400px;
}

.outline-title {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a2e;
  margin: 0 0 12px 0;
}

.outline-info {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.outline-section {
  margin-bottom: 14px;
}

.outline-label {
  font-size: 13px;
  font-weight: 600;
  color: #555;
  display: block;
  margin-bottom: 6px;
}

.outline-tag {
  margin-right: 6px;
  margin-bottom: 4px;
}

.module-list {
  padding-left: 4px;
}

.module-item {
  font-size: 13px;
  color: #444;
  padding: 4px 0;
  border-bottom: 1px solid #f0f0f0;
}

.module-item:last-child {
  border-bottom: none;
}

.feature-list {
  max-height: 200px;
  overflow-y: auto;
  padding-left: 4px;
}

.feature-item {
  font-size: 13px;
  color: #555;
  padding: 3px 0;
}

.outline-actions {
  margin-top: 16px;
}

.doc-config-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.doc-config-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.doc-config-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;
  overflow: hidden;
  transition: all 0.3s ease;
}

.doc-config-card.is-active {
  border-color: #409eff;
  background: #f0f7ff;
}

.doc-config-header {
  padding: 10px 14px;
}

.doc-config-checkbox {
  margin-right: 0;
  width: 100%;
}

.doc-config-label {
  font-weight: bold;
  color: #303133;
}

.doc-config-body {
  padding: 0 14px 12px 38px;
}

.outline-btns {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

/* ── 产出物卡片 ──────────────────────────── */
.artifact-bubble {
  max-width: 90%;
}

.artifact-card {
  background: #fff;
  border: 1px solid #e0e7ff;
  border-radius: 12px;
  overflow: hidden;
}

.artifact-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f8f9fe;
  border-bottom: 1px solid #e8ecf1;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.artifact-title {
  flex: 1;
}

.artifact-content {
  padding: 16px;
  max-height: 500px;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.7;
}

.artifact-footer {
  padding: 10px 16px;
  border-top: 1px solid #e8ecf1;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.artifact-export {
  padding: 20px 16px;
  text-align: center;
}

.export-desc {
  color: #606266;
  font-size: 13px;
  margin-bottom: 12px;
}

.export-download-link {
  text-decoration: none;
}

/* ── 打字指示器 ──────────────────────────── */
.typing-indicator {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.typing-dots {
  display: flex;
  gap: 4px;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e8ecf1;
  border-radius: 4px 16px 16px 16px;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  background: #999;
  border-radius: 50%;
  animation: typing-bounce 1.4s ease-in-out infinite;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-6px); opacity: 1; }
}

/* ── 底部输入区域 ────────────────────────── */
.input-area {
  padding: 12px 24px 16px;
  background: #fff;
  border-top: 1px solid #e8ecf1;
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  max-width: 800px;
  margin: 0 auto;
}

.input-wrapper :deep(.el-textarea__inner) {
  border-radius: 12px;
  padding: 10px 16px;
  font-size: 14px;
  resize: none;
  border: 1px solid #dcdfe6;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}

.input-wrapper :deep(.el-textarea__inner:focus) {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.15);
}

.send-btn {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
}

.input-hint {
  text-align: center;
  font-size: 11px;
  color: #bbb;
  margin-top: 6px;
}

/* ── Markdown 渲染样式 ───────────────────── */
.markdown-body :deep(h1) { font-size: 20px; font-weight: 700; margin: 16px 0 8px; color: #1a1a2e; }
.markdown-body :deep(h2) { font-size: 17px; font-weight: 600; margin: 14px 0 6px; color: #1a1a2e; }
.markdown-body :deep(h3) { font-size: 15px; font-weight: 600; margin: 12px 0 4px; color: #333; }
.markdown-body :deep(h4) { font-size: 14px; font-weight: 600; margin: 10px 0 4px; color: #444; }
.markdown-body :deep(strong) { font-weight: 600; }

.markdown-body :deep(.code-block) {
  background: #f6f8fa;
  border-radius: 8px;
  padding: 12px 16px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
  margin: 8px 0;
}

.markdown-body :deep(.inline-code) {
  background: #f0f2f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: #c7254e;
}

.markdown-body :deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 12px;
}

.markdown-body :deep(.md-table th) {
  background: #f8f9fa;
  padding: 6px 10px;
  text-align: left;
  border: 1px solid #e0e0e0;
  font-weight: 600;
}

.markdown-body :deep(.md-table td) {
  padding: 6px 10px;
  border: 1px solid #e0e0e0;
}

.markdown-body :deep(ul) {
  padding-left: 20px;
  margin: 4px 0;
}

.markdown-body :deep(li) {
  margin-bottom: 2px;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #e0e0e0;
  margin: 12px 0;
}

.markdown-body :deep(.mermaid-block) {
  background: #f8f9fe;
  border: 1px solid #e0e7ff;
  border-radius: 8px;
  padding: 16px;
  margin: 8px 0;
  overflow-x: auto;
}

.markdown-body :deep(.mermaid-fallback) {
  font-size: 13px;
}

.markdown-body :deep(.mermaid-fallback-msg) {
  color: #909399;
  margin-bottom: 8px;
}

.markdown-body :deep(.mermaid-fallback-msg a) {
  color: #409eff;
  text-decoration: none;
}

.markdown-body :deep(.mermaid-fallback-code) {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 12px;
  overflow-x: auto;
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: #303133;
  white-space: pre;
}

/* ── 文件上传相关 ──────────────────────────── */

.hidden-file-input {
  display: none;
}

.upload-btn {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border: 1px solid #dcdfe6;
  color: #606266;
  transition: all 0.2s;
}

.upload-btn:hover:not(:disabled) {
  color: #409eff;
  border-color: #409eff;
  background: #f0f7ff;
}

.file-pending-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 800px;
  margin: 0 auto 8px;
  padding: 8px 12px;
  background: #f0f7ff;
  border: 1px solid #d4e5ff;
  border-radius: 10px;
  animation: slideDown 0.2s ease-out;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.file-pending-info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.file-pending-name {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 300px;
}

.file-pending-size {
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
}

.file-pending-close {
  flex-shrink: 0;
  border: none !important;
  background: transparent !important;
  color: #909399 !important;
}

.file-pending-close:hover {
  color: #f56c6c !important;
}

/* ── 文件消息气泡 ──────────────────────────── */

.file-bubble {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #409eff, #337ecc);
  border-radius: 16px 16px 4px 16px;
  color: #fff;
  min-width: 200px;
  max-width: 360px;
}

.file-bubble-icon {
  width: 44px;
  height: 44px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.file-bubble-info {
  min-width: 0;
}

.file-bubble-name {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}

.file-bubble-meta {
  font-size: 12px;
  opacity: 0.85;
  display: flex;
  align-items: center;
  gap: 2px;
  flex-wrap: wrap;
}

.file-meta-sep {
  margin: 0 2px;
}

/* ── 敏捷进度轴 ────────────────────────────── */
.agile-stepper {
  display: flex;
  justify-content: space-between;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e8ecf1;
  position: sticky;
  top: 0;
  z-index: 10;
}

.stage-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  flex: 1;
  cursor: pointer;
  transition: all 0.3s;
}

.stage-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #f5f7fa;
  border: 2px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
  font-size: 18px;
  margin-bottom: 6px;
  position: relative;
  transition: all 0.3s;
}

.stage-node.active .stage-icon-wrap {
  background: #ecf5ff;
  border-color: #409eff;
  color: #409eff;
  box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.1);
}

.stage-node.success .stage-icon-wrap {
  background: #f0f9eb;
  border-color: #67c23a;
  color: #67c23a;
}

.stage-check {
  position: absolute;
  right: -4px;
  bottom: -4px;
  color: #67c23a;
  background: #fff;
  border-radius: 50%;
  font-size: 14px;
  line-height: 1;
}

.stage-label {
  font-size: 12px;
  font-weight: 500;
  color: #606266;
  white-space: nowrap;
}

.stage-node.active .stage-label {
  color: #409eff;
  font-weight: 600;
}

.stage-line {
  position: absolute;
  top: 18px;
  left: calc(50% + 24px);
  right: calc(-50% + 24px);
  height: 2px;
  background: #e4e7ed;
  z-index: -1;
}

.stage-node.success .stage-line {
  background: #67c23a;
}

/* ── 模式选择卡片 ──────────────────────────── */
.mode-selector-wrap {
  display: flex;
  gap: 20px;
  justify-content: center;
  margin: 32px 0;
}

.mode-card {
  flex: 1;
  max-width: 240px;
  padding: 24px;
  background: #fff;
  border: 1px solid #e8ecf1;
  border-radius: 16px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  text-align: left;
}

.mode-card:hover {
  transform: translateY(-8px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08);
}

.mode-card.free:hover { border-color: #409eff; }
.mode-card.agile:hover { border-color: #67c23a; }

.mode-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  margin-bottom: 16px;
}

.free .mode-icon { background: #ecf5ff; color: #409eff; }
.agile .mode-icon { background: #f0f9eb; color: #67c23a; }

.mode-name {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px 0;
  color: #1a1a2e;
}

.mode-intro {
  font-size: 13px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 16px;
  min-height: 60px;
}

/* ── 环节大纲面板 ────────────────────────── */
.stage-outline-panel {
  background: #f8fafc;
  border-bottom: 1px solid #e8ecf1;
  margin: 0 24px;
  border-radius: 0 0 12px 12px;
}

.stage-outline-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
}

.stage-outline-toggle {
  font-size: 14px;
  color: #909399;
  transition: transform 0.2s;
}

.stage-outline-toggle.collapsed {
  transform: rotate(-90deg);
}

.stage-outline-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.stage-outline-count {
  font-size: 12px;
  color: #909399;
  margin-left: auto;
}

.stage-outline-body {
  padding: 0 16px 16px;
  max-height: 320px;
  overflow-y: auto;
}

.stage-outline-item {
  background: #fff;
  border: 1px solid #e8ecf1;
  border-radius: 8px;
  margin-bottom: 8px;
  overflow: hidden;
}

.stage-outline-item:last-child {
  margin-bottom: 0;
}

.stage-outline-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  flex-wrap: wrap;
}

.stage-outline-item-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  min-width: 0;
}

.stage-outline-export {
  margin-left: auto;
}

.stage-outline-item-body {
  padding: 12px 14px;
  border-top: 1px solid #f0f0f0;
  font-size: 13px;
  line-height: 1.6;
  max-height: 300px;
  overflow-y: auto;
}

/* ── 环节完成确认卡片 ────────────────────── */
.stage-confirm-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: linear-gradient(135deg, #f0f9eb 0%, #e8f5e9 100%);
  border-top: 1px solid #e1f3d8;
  gap: 16px;
  flex-wrap: wrap;
}

.stage-confirm-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stage-confirm-icon {
  font-size: 24px;
  color: #67c23a;
  flex-shrink: 0;
}

.stage-confirm-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stage-confirm-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.stage-confirm-desc {
  font-size: 13px;
  color: #606266;
}

.stage-confirm-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

/* ── 里程碑卡片 ──────────────────────────── */
.milestone-bubble {
  max-width: 90%;
}

.milestone-card {
  background: #fff;
  border: 1px solid #e1f3d8;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(103, 194, 58, 0.05);
}

.milestone-header {
  padding: 12px 16px;
  background: #f0f9eb;
  border-bottom: 1px solid #e1f3d8;
  display: flex;
  align-items: center;
  gap: 8px;
}

.milestone-header .el-icon {
  color: #67c23a;
  font-size: 18px;
}

.milestone-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  flex: 1;
}

.milestone-body {
  padding: 16px;
  font-size: 14px;
  line-height: 1.7;
}

.milestone-footer {
  padding: 10px 16px;
  background: #fafafa;
  border-top: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.milestone-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.milestone-tip {
  font-size: 12px;
  color: #909399;
  font-style: italic;
}

/* ── 消息选择导出模式 ──────────────────────── */

.select-mode-msg {
  position: relative;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 2px solid transparent;
  border-radius: 12px;
}

.select-mode-msg:hover {
  border-color: #dcdfe6;
  background-color: #fafafa;
}

.msg-selected {
  border-color: #409eff !important;
  background: #f0f7ff !important;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
}

.msg-select-checkbox {
  position: absolute;
  left: -12px;
  top: 12px;
  z-index: 2;
  transform: scale(1.1);
}

.export-select-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: #ffffff;
  border-top: 1px solid #e4e7ed;
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.05);
  gap: 16px;
  border-radius: 12px 12px 0 0;
  margin: 0 16px;
  position: relative;
  top: -16px;
}

.export-select-left {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.export-select-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.export-icon {
  font-size: 18px;
  color: #409eff;
}

.export-select-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.export-select-count {
  font-size: 13px;
  color: #67c23a;
  background: #f0f9eb;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.export-select-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.export-select-controls .el-button {
  padding: 0 4px;
  font-size: 13px;
}

.export-select-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.export-format-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f5f7fa;
  padding: 4px 6px;
  border-radius: 6px;
}

.format-label {
  font-size: 14px;
  color: #606266;
  margin-left: 6px;
}

.export-format-group {
  flex-shrink: 0;
}

.export-select-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

/* ── 响应式 ──────────────────────────────── */
@media (max-width: 768px) {
  .chat-sidebar {
    display: none;
  }
  .message-bubble {
    max-width: 90%;
  }
  .outline-card {
    min-width: auto;
  }
  @media (max-width: 768px) {
    .export-select-bar {
      flex-direction: column;
      align-items: flex-start;
      gap: 16px;
      margin: 0;
      top: 0;
      border-radius: 0;
    }
    .export-select-right {
      width: 100%;
      flex-direction: column;
      align-items: stretch;
      gap: 12px;
    }
    .export-select-actions {
      justify-content: flex-end;
    }
  }
}
</style>
