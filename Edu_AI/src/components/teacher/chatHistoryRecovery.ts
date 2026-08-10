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
