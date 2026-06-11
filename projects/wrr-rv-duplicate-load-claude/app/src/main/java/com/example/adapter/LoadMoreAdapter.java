package com.example.adapter;

import android.view.*;
import android.widget.TextView;
import androidx.recyclerview.widget.RecyclerView;
import java.util.*;

public class LoadMoreAdapter extends RecyclerView.Adapter<LoadMoreAdapter.ViewHolder> {
    private List<String> items = new ArrayList<>();
    private boolean isLoading = false;

    public void addItems(List<String> newItems) {
        // BUG: no deduplication, can add same items multiple times
        items.addAll(newItems);
        notifyDataSetChanged();
    }

    public void onLoadMore() {
        if (!isLoading) {
            isLoading = true;
            // BUG: no debounce, rapid scroll triggers multiple loads
            fetchNextPage();
        }
    }

    private void fetchNextPage() { /* network call */ }

    @Override public ViewHolder onCreateViewHolder(ViewGroup p, int v) { return null; }
    @Override public void onBindViewHolder(ViewHolder h, int p) { }
    @Override public int getItemCount() { return items.size(); }

    static class ViewHolder extends RecyclerView.ViewHolder {
        ViewHolder(View v) { super(v); }
    }
}
