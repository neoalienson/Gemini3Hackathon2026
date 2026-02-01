'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Layout from '@/components/Layout';
import { Dashboard } from '@/lib/types';
import { ArrowRight } from 'lucide-react';
import { useUser } from '@/contexts/UserContext';

export default function DashboardsPage() {
  const { user } = useUser();
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    if (user) {
      fetchDashboards();
    }
  }, [user]);

  const fetchDashboards = async () => {
    if (!user) return;
    
    try {
      const response = await fetch('/api/dashboards', {
        headers: {
          'x-user-id': user.id,
        },
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch dashboards: ${response.status}`);
      }
      
      const data = await response.json();
      // Ensure data is an array
      setDashboards(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Error fetching dashboards:', error);
      setDashboards([]); // Set to empty array on error
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <div className="glass rounded-xl p-6">
            <h1 className="text-3xl font-bold text-soft-mint mb-2">Dashboards</h1>
            <p className="text-cream mt-1">
              Build and manage interactive dashboards
            </p>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12 text-white">Loading...</div>
        ) : dashboards.length === 0 ? (
          <div className="text-center py-12 text-white">
            <p className="text-cream">No dashboards found.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {dashboards.map((dashboard) => (
              <div
                key={dashboard.id}
                className="glass rounded-xl p-6 hover:glass-strong transition-all"
              >
                <h3 className="text-lg font-semibold text-soft-mint mb-2">
                  {dashboard.name}
                </h3>
                <p className="text-sm text-cream mb-4 line-clamp-2">
                  {dashboard.description}
                </p>
                <div className="flex items-center justify-between text-xs text-cream mb-4">
                  <span>
                    {dashboard.widgets.length} widget
                    {dashboard.widgets.length !== 1 ? 's' : ''}
                  </span>
                  <span>
                    Updated {new Date(dashboard.updatedAt).toLocaleDateString()}
                  </span>
                </div>
                <button
                  onClick={() => router.push(`/dashboards/${dashboard.id}`)}
                  className="w-full glass-strong px-4 py-2 rounded-lg text-white hover:glass-active transition-all flex items-center justify-center gap-2"
                >
                  Open Dashboard
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
