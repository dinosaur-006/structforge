/** Map technical error patterns to user-friendly Chinese messages. */
export function humanizeError(message: string): string {
  const msg = message.toLowerCase();

  if (msg.includes('failed to fetch') || msg.includes('networkerror'))
    return '无法连接到服务器，请检查网络或确认后端已启动';
  if (msg.includes('timeout') || msg.includes('timed out'))
    return '请求超时，服务器可能负载较高，请稍后重试';
  if (msg.includes('401') || msg.includes('unauthorized'))
    return 'API Key 无效或未配置，请检查 .env 文件';
  if (msg.includes('404') || msg.includes('not found'))
    return '请求的资源不存在，可能已被删除';
  if (msg.includes('422') || msg.includes('unprocessable'))
    return '输入数据格式有误，请检查填写内容';
  if (msg.includes('429') || msg.includes('rate limit'))
    return '请求太频繁，请稍等片刻再试';
  if (msg.includes('500') || msg.includes('internal server'))
    return '服务器内部错误，请稍后重试';
  if (msg.includes('503') || msg.includes('unavailable'))
    return '服务暂时不可用，正在自动重试...';

  // LLM/script generation errors
  if (msg.includes('finalscript') && msg.includes('segment'))
    return 'AI生成的脚本格式异常，请点击重试或更换风格后重新生成';
  if (msg.includes('structure') && msg.includes('initializ'))
    return '项目数据未就绪，请先完成视频分析';
  if (msg.includes('failed to extract') || msg.includes('keyframes'))
    return '视频格式不支持，请上传 MP4 格式的视频文件';
  if (msg.includes('llm failed') || msg.includes('structureextraction'))
    return 'AI分析遇到问题，已自动使用基础分析模式';
  if (msg.includes('migration') && msg.includes('attempts'))
    return 'AI脚本生成多次失败，请稍后重试或更换商品信息';

  // Fallback: return the original but truncated
  if (message.length > 100)
    return message.substring(0, 97) + '...';
  return message;
}
