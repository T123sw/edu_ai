import React, { useState } from 'react';
import { Card, Input, Button, message, Spin, List, Typography, Tag, Space, Divider } from 'antd';
import { SearchOutlined, ReloadOutlined, FileTextOutlined, LinkOutlined } from '@ant-design/icons';
import { deepSearchAndCrawl, getCrawlResults, CrawlResult } from '../services/deepsearch';
import './DeepSearchPage.css';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

interface SearchState {
  loading: boolean;
  batchId: string | null;
  query: string;
  links: string[];
  results: CrawlResult[];
  successCount: number;
  failedCount: number;
}

const DeepSearchPage: React.FC = () => {
  const [query, setQuery] = useState('');
  const [maxUrls, setMaxUrls] = useState<number>(5);
  const [state, setState] = useState<SearchState>({
    loading: false,
    batchId: null,
    query: '',
    links: [],
    results: [],
    successCount: 0,
    failedCount: 0,
  });

  const handleSearch = async () => {
    if (!query.trim()) {
      message.warning('请输入搜索关键词');
      return;
    }

    setState({
      loading: true,
      batchId: null,
      query: query.trim(),
      links: [],
      results: [],
      successCount: 0,
      failedCount: 0,
    });

    try {
      message.info('开始深度搜索和爬取，这可能需要几分钟时间...', 10);
      
      console.log('发送搜索请求:', { query: query.trim(), max_urls: maxUrls });
      const response = await deepSearchAndCrawl({
        query: query.trim(),
        max_urls: maxUrls,
        crawl_timeout: 30,
      });

      console.log('搜索响应:', response);

      if (!response.ok) {
        message.error(response.message || '搜索失败');
        setState(prev => ({ ...prev, loading: false }));
        return;
      }

      if (!response.batch_id) {
        message.warning('未找到相关链接');
        setState(prev => ({ ...prev, loading: false }));
        return;
      }

      // 如果响应中已经包含结果，直接使用；否则获取详细结果
      if (response.results && response.results.length > 0) {
        // 响应中已包含结果
        setState({
          loading: false,
          batchId: response.batch_id!,
          query: response.query || query.trim(),
          links: response.links || [],
          results: response.results,
          successCount: response.success_count || 0,
          failedCount: response.failed_count || 0,
        });
        message.success(`搜索完成！成功: ${response.success_count}, 失败: ${response.failed_count}`);
      } else {
        // 需要获取详细结果
        message.success('搜索完成，正在获取详细结果...', 3);
        console.log('获取详细结果，batch_id:', response.batch_id);
        const resultsResponse = await getCrawlResults(response.batch_id!);
        
        console.log('详细结果响应:', resultsResponse);
        
        if (resultsResponse.ok && resultsResponse.results) {
          setState({
            loading: false,
            batchId: response.batch_id!,
            query: response.query || query.trim(),
            links: response.links || [],
            results: resultsResponse.results,
            successCount: resultsResponse.success_count || 0,
            failedCount: resultsResponse.failed_count || 0,
          });
          message.success(`搜索完成！成功: ${resultsResponse.success_count}, 失败: ${resultsResponse.failed_count}`);
        } else {
          setState({
            loading: false,
            batchId: response.batch_id!,
            query: response.query || query.trim(),
            links: response.links || [],
            results: [],
            successCount: 0,
            failedCount: 0,
          });
          message.warning(resultsResponse.message || '获取结果详情失败');
        }
      }
    } catch (error: any) {
      console.error('搜索错误:', error);
      const errorMessage = error.message || '未知错误';
      message.error(`搜索失败: ${errorMessage}`);
      setState(prev => ({ ...prev, loading: false }));
    }
  };

  const handleRefresh = async () => {
    if (!state.batchId) return;

    setState(prev => ({ ...prev, loading: true }));
    try {
      const resultsResponse = await getCrawlResults(state.batchId);
      if (resultsResponse.ok && resultsResponse.results) {
        setState(prev => ({
          ...prev,
          loading: false,
          results: resultsResponse.results || [],
          successCount: resultsResponse.success_count || 0,
          failedCount: resultsResponse.failed_count || 0,
        }));
        message.success('结果已更新');
      }
    } catch (error: any) {
      message.error(`刷新失败: ${error.message}`);
      setState(prev => ({ ...prev, loading: false }));
    }
  };

  return (
    <div className="deep-search-page">
      <Card className="search-card">
        <Title level={2}>深度搜索与内容爬取</Title>
        <Paragraph>
          输入搜索关键词，系统将自动搜索相关链接并爬取内容，清洗后展示给您。
        </Paragraph>

        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <Text strong>搜索关键词：</Text>
            <TextArea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="例如：计算思维 课程大纲 PDF"
              rows={3}
              disabled={state.loading}
            />
          </div>

          <div>
            <Text strong>最大URL数量：</Text>
            <Input
              type="number"
              value={maxUrls}
              onChange={(e) => setMaxUrls(parseInt(e.target.value) || 5)}
              min={1}
              max={20}
              style={{ width: 120 }}
              disabled={state.loading}
            />
            <Text type="secondary" style={{ marginLeft: 8 }}>
              (建议5-10个，过多可能耗时较长)
            </Text>
          </div>

          <Button
            type="primary"
            icon={<SearchOutlined />}
            onClick={handleSearch}
            loading={state.loading}
            size="large"
            block
          >
            开始搜索并爬取
          </Button>
        </Space>
      </Card>

      {state.loading && (
        <Card className="results-card">
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16 }}>
              <Text>正在搜索和爬取内容，请耐心等待...</Text>
            </div>
          </div>
        </Card>
      )}

      {!state.loading && state.batchId && (
        <>
          <Card className="summary-card">
            <Space split={<Divider type="vertical" />}>
              <div>
                <Text type="secondary">查询：</Text>
                <Text strong>{state.query}</Text>
              </div>
              <div>
                <Text type="secondary">批次ID：</Text>
                <Text code>{state.batchId}</Text>
              </div>
              <div>
                <Text type="secondary">成功：</Text>
                <Tag color="success">{state.successCount}</Tag>
              </div>
              <div>
                <Text type="secondary">失败：</Text>
                <Tag color="error">{state.failedCount}</Tag>
              </div>
              <Button
                icon={<ReloadOutlined />}
                onClick={handleRefresh}
                size="small"
              >
                刷新结果
              </Button>
            </Space>
          </Card>

          {state.links.length > 0 && (
            <Card className="links-card" title={<><LinkOutlined /> 搜索到的链接</>}>
              <List
                dataSource={state.links}
                renderItem={(link, index) => (
                  <List.Item>
                    <Text>{index + 1}. </Text>
                    <a href={link} target="_blank" rel="noopener noreferrer">
                      {link}
                    </a>
                  </List.Item>
                )}
              />
            </Card>
          )}

          {state.results.length > 0 && (
            <Card className="results-card" title={<><FileTextOutlined /> 爬取结果</>}>
              <List
                dataSource={state.results}
                renderItem={(result, index) => (
                  <List.Item key={index}>
                    <Card
                      size="small"
                      style={{ width: '100%' }}
                      title={
                        <Space>
                          <a href={result.url} target="_blank" rel="noopener noreferrer">
                            {result.title || result.url}
                          </a>
                          <Tag color={result.status === 'success' ? 'success' : 'error'}>
                            {result.status}
                          </Tag>
                          {result.content_type && (
                            <Tag>{result.content_type}</Tag>
                          )}
                        </Space>
                      }
                    >
                      {result.status === 'success' && result.content && (
                        <div>
                          <Paragraph
                            ellipsis={{ rows: 5, expandable: true, symbol: '展开' }}
                            style={{ marginBottom: 0 }}
                          >
                            {result.content}
                          </Paragraph>
                          {result.metadata && Object.keys(result.metadata).length > 0 && (
                            <div style={{ marginTop: 8 }}>
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                元数据: {JSON.stringify(result.metadata, null, 2)}
                              </Text>
                            </div>
                          )}
                        </div>
                      )}
                      {result.status === 'failed' && result.error_message && (
                        <Text type="danger">错误: {result.error_message}</Text>
                      )}
                    </Card>
                  </List.Item>
                )}
              />
            </Card>
          )}
        </>
      )}
    </div>
  );
};

export default DeepSearchPage;

