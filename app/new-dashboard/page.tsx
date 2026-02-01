'use client';

import { useState, useRef, useEffect } from 'react';
import dynamic from 'next/dynamic';
import ReactMarkdown from 'react-markdown';
import Layout from '@/components/Layout';

const ReactECharts = dynamic(() => import('echarts-for-react'), { ssr: false });
import { Dashboard, Widget } from '@/lib/types';
import { Send, Loader, Sparkles } from 'lucide-react';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

const COLORS = ['#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export default function NewDashboardPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [dashboard, setDashboard] = useState<Partial<Dashboard> | null>(null);
  const [visualizationCharts, setVisualizationCharts] = useState<Array<{ title?: string; echartsConfig: object; data?: unknown[]; chartType?: string }>>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const hasMessages = messages.length > 0;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!hasMessages && inputRef.current) {
      inputRef.current.focus();
    }
  }, [hasMessages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setVisualizationCharts([]);

    const isFirstMessage = messages.length === 0;
    const assistantId = (Date.now() + 1).toString();
    let content = '';
    const progressLines: string[] = [];

    const assistantMessage: Message = {
      id: assistantId,
      role: 'assistant',
      content: 'Generating query plan...',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, assistantMessage]);

    try {
      const res = await fetch('/api/insight-exploration', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMessage.content }),
      });

      if (!res.ok || !res.body) {
        const err = await res.text();
        throw new Error(err || 'Request failed');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const chunk = JSON.parse(line);
            if (chunk.type === 'query_plan') {
              content = `## Query Plan\n\n${chunk.content || ''}\n\n---\n\n**Progress:**\n`;
              progressLines.length = 0;
            } else if (chunk.type === 'progress') {
              progressLines.push(`- ${chunk.message || 'Running...'}`);
              content = content.replace(/---\n\n\*\*Progress:\*\*\n[\s\S]*$/, '') +
                `---\n\n**Progress:**\n${progressLines.join('\n')}`;
            } else if (chunk.type === 'final_answer') {
              content = content + `\n\n---\n\n## Answer\n\n${chunk.content || ''}`;
            } else if (chunk.type === 'visualization' && Array.isArray(chunk.charts)) {
              setVisualizationCharts(chunk.charts);
            } else if (chunk.type === 'error') {
              content = content ? `${content}\n\n**Error:** ${chunk.content}` : `Error: ${chunk.content}`;
            }
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: content || m.content } : m
              )
            );
          } catch (_) {
            // skip malformed lines
          }
        }
      }

      if (!content) {
        content = generateAIResponse(userMessage.content, isFirstMessage);
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content } : m))
        );
      }

      if (isFirstMessage) {
        setDashboard(generateDashboardFromDescription(userMessage.content));
      } else {
        setDashboard(updateDashboardFromMessage(userMessage.content, dashboard));
      }
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : 'Something went wrong';
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, content: `Error: ${errMsg}` } : m
        )
      );
      if (isFirstMessage) {
        setDashboard(generateDashboardFromDescription(userMessage.content));
      } else {
        setDashboard(updateDashboardFromMessage(userMessage.content, dashboard));
      }
    } finally {
      setIsLoading(false);
    }
  };

  const generateAIResponse = (userInput: string, isFirstMessage: boolean): string => {
    const lowerInput = userInput.toLowerCase();
    
    if (isFirstMessage) {
      if (lowerInput.includes('sales') || lowerInput.includes('revenue')) {
        return "I've created a sales dashboard with revenue trends, monthly breakdowns, and product performance metrics. You can ask me to add more charts, change colors, or modify any aspect of the dashboard.";
      } else if (lowerInput.includes('user') || lowerInput.includes('customer')) {
        return "I've created a user analytics dashboard showing user growth, engagement metrics, and demographic breakdowns. What would you like to adjust?";
      } else if (lowerInput.includes('financial') || lowerInput.includes('finance')) {
        return "I've created a financial dashboard with profit/loss trends, expense breakdowns, and cash flow metrics. Feel free to ask for modifications!";
      } else {
        return "I've created a dashboard based on your description. The canvas on the right shows a preview. You can ask me to add charts, change layouts, modify colors, or adjust any aspect of the dashboard.";
      }
    } else {
      // Follow-up messages
      if (lowerInput.includes('add') || lowerInput.includes('more')) {
        return "I've added a new widget to your dashboard. Check the canvas on the right to see the update!";
      } else if (lowerInput.includes('change') || lowerInput.includes('modify') || lowerInput.includes('update')) {
        return "I've updated the dashboard based on your request. The changes are reflected in the canvas.";
      } else if (lowerInput.includes('color') || lowerInput.includes('theme')) {
        return "I've updated the color scheme of your dashboard. The new colors are now applied to all charts.";
      } else if (lowerInput.includes('remove') || lowerInput.includes('delete')) {
        return "I've removed the requested widget from your dashboard.";
      } else {
        return "I've made the requested changes to your dashboard. Check the canvas to see the updates!";
      }
    }
  };

  const updateDashboardFromMessage = (
    message: string,
    currentDashboard: Partial<Dashboard> | null
  ): Partial<Dashboard> => {
    if (!currentDashboard) {
      return generateDashboardFromDescription(message);
    }

    const lowerMessage = message.toLowerCase();
    const updatedWidgets = [...(currentDashboard.widgets || [])];

    if (lowerMessage.includes('add') || lowerMessage.includes('more')) {
      // Add a new widget
      const newWidget: Widget = {
        id: `widget-${Date.now()}`,
        type: 'bar',
        title: 'New Chart',
        config: {},
        x: 0,
        y: updatedWidgets.length * 4,
        width: 6,
        height: 4,
      };
      updatedWidgets.push(newWidget);
    } else if (lowerMessage.includes('remove') || lowerMessage.includes('delete')) {
      // Remove the last widget
      if (updatedWidgets.length > 0) {
        updatedWidgets.pop();
      }
    }

    return {
      ...currentDashboard,
      widgets: updatedWidgets,
    };
  };

  const generateDashboardFromDescription = (description: string): Partial<Dashboard> => {
    const lowerDesc = description.toLowerCase();
    
    const widgets: Widget[] = [];
    
    if (lowerDesc.includes('sales') || lowerDesc.includes('revenue')) {
      widgets.push(
        {
          id: 'widget-1',
          type: 'metric',
          title: 'Total Revenue',
          config: { value: 1250000 },
          x: 0,
          y: 0,
          width: 4,
          height: 2,
        },
        {
          id: 'widget-2',
          type: 'line',
          title: 'Revenue Trend',
          config: {},
          x: 4,
          y: 0,
          width: 8,
          height: 4,
        },
        {
          id: 'widget-3',
          type: 'bar',
          title: 'Monthly Sales',
          config: {},
          x: 0,
          y: 2,
          width: 6,
          height: 4,
        },
        {
          id: 'widget-4',
          type: 'pie',
          title: 'Product Distribution',
          config: {},
          x: 6,
          y: 2,
          width: 6,
          height: 4,
        }
      );
    } else if (lowerDesc.includes('user') || lowerDesc.includes('customer')) {
      widgets.push(
        {
          id: 'widget-1',
          type: 'metric',
          title: 'Total Users',
          config: { value: 45230 },
          x: 0,
          y: 0,
          width: 4,
          height: 2,
        },
        {
          id: 'widget-2',
          type: 'line',
          title: 'User Growth',
          config: {},
          x: 4,
          y: 0,
          width: 8,
          height: 4,
        },
        {
          id: 'widget-3',
          type: 'bar',
          title: 'Active Users by Region',
          config: {},
          x: 0,
          y: 2,
          width: 12,
          height: 4,
        }
      );
    } else {
      // Default dashboard
      widgets.push(
        {
          id: 'widget-1',
          type: 'metric',
          title: 'Key Metric',
          config: { value: 10000 },
          x: 0,
          y: 0,
          width: 4,
          height: 2,
        },
        {
          id: 'widget-2',
          type: 'line',
          title: 'Trend Analysis',
          config: {},
          x: 4,
          y: 0,
          width: 8,
          height: 4,
        },
        {
          id: 'widget-3',
          type: 'bar',
          title: 'Category Breakdown',
          config: {},
          x: 0,
          y: 2,
          width: 6,
          height: 4,
        },
        {
          id: 'widget-4',
          type: 'pie',
          title: 'Distribution',
          config: {},
          x: 6,
          y: 2,
          width: 6,
          height: 4,
        }
      );
    }

    return {
      name: 'New Dashboard',
      description: description,
      widgets,
    };
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Mock data for charts
  const mockData = [
    { month: 'Jan', value: 125000 },
    { month: 'Feb', value: 142000 },
    { month: 'Mar', value: 138000 },
    { month: 'Apr', value: 155000 },
    { month: 'May', value: 148000 },
    { month: 'Jun', value: 162000 },
  ];

  const pieData = [
    { name: 'Category A', value: 400 },
    { name: 'Category B', value: 300 },
    { name: 'Category C', value: 200 },
    { name: 'Category D', value: 100 },
  ];

  return (
    <Layout>
      <div className="h-full flex flex-col">
        {!hasMessages ? (
          // Centered chat interface (initial state)
          <div className="flex-1 flex items-center justify-center p-8">
            <div className="w-full max-w-3xl">
              <div className="text-center mb-12 animate-fade-in">
                <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl glass-strong mb-6 shadow-lg">
                  <Sparkles className="w-10 h-10 text-blue-400" />
                </div>
                <h1 className="text-4xl font-bold text-soft-mint mb-4 bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
                  Create Your Dashboard
                </h1>
                <p className="text-white text-xl mb-2">
                  Describe what you'd like to visualize
                </p>
                <p className="text-white text-base">
                  I'll build an interactive dashboard for you
                </p>
              </div>
              <div className="relative animate-slide-up">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="e.g., Create a sales dashboard with revenue trends, monthly breakdowns, and product performance metrics..."
                  className="w-full px-6 py-5 pr-16 text-lg text-white glass rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 resize-none placeholder:text-white transition-all shadow-xl"
                  rows={5}
                />
                <button
                  onClick={handleSend}
                  disabled={!input.trim() || isLoading}
                  className="absolute right-4 bottom-4 p-3 glass-strong text-white rounded-xl hover:glass-active hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 transition-all shadow-lg"
                >
                  {isLoading ? (
                    <Loader className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </button>
              </div>
              <div className="mt-6 flex flex-wrap gap-3 justify-center">
                <button
                  onClick={() => setInput('Create a sales dashboard with revenue trends and monthly breakdowns')}
                  className="px-4 py-2 text-sm glass rounded-lg text-pale-gold hover:glass-strong hover:text-white transition-all"
                >
                  Sales Dashboard
                </button>
                <button
                  onClick={() => setInput('Create a user analytics dashboard showing growth and engagement metrics')}
                  className="px-4 py-2 text-sm glass rounded-lg text-pale-gold hover:glass-strong hover:text-white transition-all"
                >
                  User Analytics
                </button>
                <button
                  onClick={() => setInput('Create a financial dashboard with profit/loss trends and expense breakdowns')}
                  className="px-4 py-2 text-sm glass rounded-lg text-pale-gold hover:glass-strong hover:text-white transition-all"
                >
                  Financial Dashboard
                </button>
              </div>
            </div>
          </div>
        ) : (
          // Split view: Chat left, Canvas right
          <div className="flex-1 flex gap-4 overflow-hidden p-4">
            {/* Chat Panel - Left */}
            <div className="w-[420px] flex flex-col glass rounded-2xl overflow-hidden shadow-xl border border-white/10">
              <div className="p-5 border-b border-white/10 bg-black/20">
                <h2 className="text-lg font-semibold text-soft-mint flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-blue-400" />
                  Chat Assistant
                </h2>
                <p className="text-xs text-white mt-1">Ask me to modify your dashboard</p>
              </div>
              <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-white/20 scrollbar-track-transparent">
                {messages.map((message, index) => (
                  <div
                    key={message.id}
                    className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
                    style={{ animationDelay: `${index * 0.1}s` }}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-lg ${
                        message.role === 'user'
                          ? 'glass-active text-white bg-gradient-to-br from-blue-500/20 to-purple-500/20'
                          : 'glass text-white'
                      }`}
                    >
                      {message.role === 'assistant' ? (
                        <div className="text-sm leading-relaxed text-white [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mt-3 [&_h2]:mb-1 [&_p]:my-1 [&_ul]:my-2 [&_li]:my-0 [&_strong]:font-semibold [&_hr]:my-2 [&_hr]:border-white/20">
                          <ReactMarkdown>{message.content}</ReactMarkdown>
                        </div>
                      ) : (
                        <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
                      )}
                      <p className={`text-xs mt-2 ${
                        message.role === 'user' ? 'text-white' : 'text-white'
                      }`}>
                        {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start animate-fade-in">
                    <div className="glass rounded-2xl px-4 py-3 shadow-lg">
                      <div className="flex items-center gap-2">
                        <Loader className="w-4 h-4 animate-spin text-blue-400" />
                        <span className="text-sm text-white">Thinking...</span>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
              <div className="p-4 border-t border-white/10 bg-black/20">
                <div className="relative">
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="Ask me to modify the dashboard..."
                    className="w-full px-4 py-3 pr-12 text-sm glass rounded-xl text-white placeholder:text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500/50 resize-none transition-all"
                    rows={2}
                  />
                  <button
                    onClick={handleSend}
                    disabled={!input.trim() || isLoading}
                    className="absolute right-2 bottom-2 p-2 glass-strong text-white rounded-lg hover:glass-active hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 transition-all"
                  >
                    {isLoading ? (
                      <Loader className="w-4 h-4 animate-spin" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Canvas Panel - Right */}
            <div className="flex-1 overflow-y-auto rounded-2xl">
              <div className="h-full p-6">
                {visualizationCharts.length > 0 ? (
                  <div className="space-y-6">
                    <div className="glass rounded-2xl p-6 shadow-xl border border-white/10">
                      <h2 className="text-2xl font-bold text-soft-mint mb-2 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                        Data Visualization
                      </h2>
                      <p className="text-white text-sm">
                        Generated visualizations from query results
                      </p>
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {visualizationCharts.map((chart, idx) => (
                        <div
                          key={idx}
                          className="glass rounded-2xl p-6 shadow-lg border border-white/10 animate-fade-in"
                          style={{ minHeight: 420 }}
                        >
                          {chart.title && (
                            <h3 className="text-lg font-semibold text-soft-mint mb-4">
                              {chart.title}
                            </h3>
                          )}
                          {chart.echartsConfig && (
                            <ReactECharts
                              option={chart.echartsConfig}
                              style={{ height: 380, width: '100%', minHeight: 380 }}
                              notMerge
                            />
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <>
                <div className="mb-6 glass rounded-2xl p-6 shadow-xl border border-white/10">
                  <h2 className="text-2xl font-bold text-soft-mint mb-2 bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                    {dashboard?.name || 'Dashboard Preview'}
                  </h2>
                  <p className="text-white">
                    {dashboard?.description || 'Your dashboard will appear here'}
                  </p>
                </div>
                {dashboard?.widgets && dashboard.widgets.length > 0 ? (
                  <div className="grid grid-cols-12 gap-4">
                    {dashboard.widgets.map((widget, index) => (
                      <div
                        key={widget.id}
                        className="glass rounded-2xl p-6 hover:glass-strong transition-all shadow-lg border border-white/10 animate-fade-in"
                        style={{
                          gridColumn: `span ${widget.width}`,
                          gridRow: `span ${widget.height}`,
                          animationDelay: `${index * 0.1}s`,
                        }}
                      >
                        <h3 className="text-lg font-semibold text-soft-mint mb-4">
                          {widget.title}
                        </h3>
                        {widget.type === 'metric' && (
                          <div className="text-4xl font-bold text-white">
                            {typeof widget.config.value === 'number'
                              ? `$${widget.config.value.toLocaleString()}`
                              : widget.config.value}
                          </div>
                        )}
                        {widget.type === 'line' && (
                          <ResponsiveContainer width="100%" height={300}>
                            <LineChart data={mockData}>
                              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                              <XAxis dataKey="month" stroke="rgba(255,255,255,0.5)" />
                              <YAxis stroke="rgba(255,255,255,0.5)" />
                              <Tooltip 
                                contentStyle={{ 
                                  backgroundColor: 'rgba(0,0,0,0.8)',
                                  border: '1px solid rgba(255,255,255,0.2)',
                                  borderRadius: '8px',
                                  color: '#fff'
                                }}
                              />
                              <Legend wrapperStyle={{ color: 'rgba(255,255,255,0.7)' }} />
                              <Line
                                type="monotone"
                                dataKey="value"
                                stroke="#6366f1"
                                strokeWidth={2}
                                dot={false}
                              />
                            </LineChart>
                          </ResponsiveContainer>
                        )}
                        {widget.type === 'bar' && (
                          <ResponsiveContainer width="100%" height={300}>
                            <BarChart data={mockData}>
                              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                              <XAxis dataKey="month" stroke="rgba(255,255,255,0.5)" />
                              <YAxis stroke="rgba(255,255,255,0.5)" />
                              <Tooltip 
                                contentStyle={{ 
                                  backgroundColor: 'rgba(0,0,0,0.8)',
                                  border: '1px solid rgba(255,255,255,0.2)',
                                  borderRadius: '8px',
                                  color: '#fff'
                                }}
                              />
                              <Legend wrapperStyle={{ color: 'rgba(255,255,255,0.7)' }} />
                              <Bar dataKey="value" fill="#6366f1" />
                            </BarChart>
                          </ResponsiveContainer>
                        )}
                        {widget.type === 'pie' && (
                          <ResponsiveContainer width="100%" height={300}>
                            <PieChart>
                              <Pie
                                data={pieData}
                                cx="50%"
                                cy="50%"
                                labelLine={false}
                                label={({ name, percent }) =>
                                  `${name} ${(percent * 100).toFixed(0)}%`
                                }
                                outerRadius={80}
                                fill="#8884d8"
                                dataKey="value"
                              >
                                {pieData.map((entry, index) => (
                                  <Cell
                                    key={`cell-${index}`}
                                    fill={COLORS[index % COLORS.length]}
                                  />
                                ))}
                              </Pie>
                              <Tooltip 
                                contentStyle={{ 
                                  backgroundColor: 'rgba(0,0,0,0.8)',
                                  border: '1px solid rgba(255,255,255,0.2)',
                                  borderRadius: '8px',
                                  color: '#fff'
                                }}
                              />
                            </PieChart>
                          </ResponsiveContainer>
                        )}
                        {widget.type === 'table' && (
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="border-b border-white/10">
                                  <th className="text-left py-2 px-4 text-white">Column 1</th>
                                  <th className="text-left py-2 px-4 text-white">Column 2</th>
                                  <th className="text-left py-2 px-4 text-white">Column 3</th>
                                </tr>
                              </thead>
                              <tbody>
                                {[1, 2, 3, 4, 5].map((i) => (
                                  <tr key={i} className="border-b border-white/10">
                                    <td className="py-2 px-4 text-white">Row {i} Col 1</td>
                                    <td className="py-2 px-4 text-white">Row {i} Col 2</td>
                                    <td className="py-2 px-4 text-white">Row {i} Col 3</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-20">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-full glass-strong mb-4">
                      <Sparkles className="w-8 h-8 text-blue-400" />
                    </div>
                    <p className="text-white text-lg">Waiting for dashboard description...</p>
                  </div>
                )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
