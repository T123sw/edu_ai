export type RecoveryDecision = {
  nextConversationId: string | null;
  clearMessages: boolean;
  clearPendingTasks: boolean;
  retryable: boolean;
};

export type ConversationRecoveryError = {
  conversationId: string;
  message: string;
  retryable: boolean;
};

export type ConversationLoadToken = Readonly<{
  generation: number;
  conversationId: string;
}>;

export type BackgroundTaskToken = Readonly<{
  contextGeneration: number;
  taskGeneration: number;
  taskId: string;
  conversationId: string | null;
}>;

export type ConversationSendToken = Readonly<{
  contextGeneration: number;
  sendGeneration: number;
  conversationId: string | null;
}>;

export type ConversationAsyncGuard = {
  startLoad: (
    conversationId: string,
    options?: { invalidateBackgroundTasks?: boolean },
  ) => ConversationLoadToken;
  invalidateLoads: (activeConversationId: string | null) => void;
  invalidateConversation: (activeConversationId: string | null) => void;
  invalidateBackgroundTasks: (activeConversationId: string | null) => void;
  restoreConversation: (activeConversationId: string | null) => void;
  adoptConversation: (activeConversationId: string | null) => void;
  isConversationActive: (conversationId: string) => boolean;
  isLatestLoad: (token: ConversationLoadToken) => boolean;
  commitLoad: (token: ConversationLoadToken, commit: () => void) => boolean;
  captureSend: (conversationId: string | null) => ConversationSendToken;
  isSendCurrent: (
    token: ConversationSendToken,
    currentConversationId: string | null,
  ) => boolean;
  commitSend: (
    token: ConversationSendToken,
    currentConversationId: string | null,
    commit: () => void,
  ) => boolean;
  bindBackgroundTaskForSend: (
    sendToken: ConversationSendToken,
    taskId: string,
    currentConversationId: string | null,
  ) => BackgroundTaskToken | null;
  bindBackgroundTask: (
    taskId: string,
    conversationId: string | null,
  ) => BackgroundTaskToken;
  commitBackgroundTask: (
    token: BackgroundTaskToken,
    currentConversationId: string | null,
    commit: () => void,
  ) => boolean;
};

export function createConversationAsyncGuard(
  initialConversationId: string | null = null,
): ConversationAsyncGuard {
  let loadGeneration = 0;
  let contextGeneration = 0;
  let taskGeneration = 0;
  let sendGeneration = 0;
  let activeConversationId = initialConversationId;

  const isLatestLoad = (token: ConversationLoadToken) => (
    token.generation === loadGeneration
  );
  const isSendCurrent = (
    token: ConversationSendToken,
    currentConversationId: string | null,
  ) => (
    token.contextGeneration === contextGeneration
    && token.sendGeneration === sendGeneration
    && activeConversationId === currentConversationId
    && (token.conversationId === null || token.conversationId === currentConversationId)
  );
  const bindBackgroundTask = (
    taskId: string,
    conversationId: string | null,
  ): BackgroundTaskToken => {
    taskGeneration += 1;
    return { contextGeneration, taskGeneration, taskId, conversationId };
  };

  return {
    startLoad(conversationId, options) {
      loadGeneration += 1;
      if (options?.invalidateBackgroundTasks !== false) {
        contextGeneration += 1;
        taskGeneration += 1;
      }
      activeConversationId = conversationId;
      return { generation: loadGeneration, conversationId };
    },
    invalidateLoads(nextConversationId) {
      loadGeneration += 1;
      activeConversationId = nextConversationId;
    },
    invalidateConversation(nextConversationId) {
      loadGeneration += 1;
      contextGeneration += 1;
      taskGeneration += 1;
      activeConversationId = nextConversationId;
    },
    invalidateBackgroundTasks(nextConversationId) {
      contextGeneration += 1;
      taskGeneration += 1;
      activeConversationId = nextConversationId;
    },
    restoreConversation(nextConversationId) {
      activeConversationId = nextConversationId;
    },
    adoptConversation(nextConversationId) {
      activeConversationId = nextConversationId;
    },
    isConversationActive(conversationId) {
      return activeConversationId === conversationId;
    },
    isLatestLoad,
    commitLoad(token, commit) {
      if (!isLatestLoad(token) || activeConversationId !== token.conversationId) {
        return false;
      }
      commit();
      return true;
    },
    captureSend(conversationId) {
      sendGeneration += 1;
      return { contextGeneration, sendGeneration, conversationId };
    },
    isSendCurrent,
    commitSend(token, currentConversationId, commit) {
      if (!isSendCurrent(token, currentConversationId)) {
        return false;
      }
      commit();
      return true;
    },
    bindBackgroundTaskForSend(sendToken, taskId, currentConversationId) {
      if (!isSendCurrent(sendToken, currentConversationId)) {
        return null;
      }
      return bindBackgroundTask(taskId, currentConversationId);
    },
    bindBackgroundTask,
    commitBackgroundTask(token, currentConversationId, commit) {
      const sameContext = token.contextGeneration === contextGeneration;
      const sameTask = token.taskGeneration === taskGeneration;
      const activeCurrentConversation = activeConversationId === currentConversationId;
      const sameBoundConversation = (
        token.conversationId === null
        || token.conversationId === currentConversationId
      );
      if (!sameContext || !sameTask || !activeCurrentConversation || !sameBoundConversation) {
        return false;
      }
      commit();
      return true;
    },
  };
}

export function resolveConversationRecoveryErrorAction(
  error: ConversationRecoveryError | null,
  action: 'dismiss' | 'retry',
): {
  nextError: ConversationRecoveryError | null;
  retryConversationId: string | null;
} {
  if (!error || action === 'dismiss') {
    return { nextError: null, retryConversationId: null };
  }
  return {
    nextError: error,
    retryConversationId: error.retryable ? error.conversationId : null,
  };
}

export type ConversationRecoveryActions = {
  clearRecoveredConversationState: () => void;
  clearPendingTasks: (nextConversationId: string | null) => void;
  setCurrentConversationId: (conversationId: string | null) => void;
  setError: (error: ConversationRecoveryError) => void;
};

export function applyConversationRecoveryFailure(
  currentConversationId: string | null,
  failedConversationId: string,
  error: Pick<ConversationRecoveryError, 'message' | 'retryable'>,
  actions: ConversationRecoveryActions,
): RecoveryDecision {
  const decision = recoverConversationFailure(currentConversationId, failedConversationId);
  if (decision.clearMessages) {
    actions.clearRecoveredConversationState();
  }
  if (decision.clearPendingTasks) {
    actions.clearPendingTasks(decision.nextConversationId);
  }
  actions.setCurrentConversationId(decision.nextConversationId);
  actions.setError({
    conversationId: failedConversationId,
    message: error.message,
    retryable: decision.retryable && error.retryable,
  });
  return decision;
}

export function recoverConversationFailure(
  currentConversationId: string | null,
  failedConversationId: string,
): RecoveryDecision {
  const activeFailed = currentConversationId === failedConversationId;
  return {
    nextConversationId: activeFailed ? null : currentConversationId,
    clearMessages: activeFailed,
    clearPendingTasks: activeFailed,
    retryable: true,
  };
}
