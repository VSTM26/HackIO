package com.aep.stormassistant

import android.content.Context
import android.graphics.Color
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.recyclerview.widget.RecyclerView

class AlertAdapter(
    private val context: Context,
    private val alerts: MutableList<AlertModel> = mutableListOf(),
    private val onItemClick: ((AlertModel) -> Unit)? = null
) : RecyclerView.Adapter<AlertAdapter.AlertViewHolder>() {

    fun updateList(newAlerts: List<AlertModel>) {
        alerts.clear()
        alerts.addAll(newAlerts)
        notifyDataSetChanged()
    }

    fun addAlert(alert: AlertModel) {
        alerts.add(0, alert)
        notifyItemInserted(0)
    }

    fun clear() {
        alerts.clear()
        notifyDataSetChanged()
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): AlertViewHolder {
        val view = LayoutInflater.from(parent.context).inflate(R.layout.item_alert, parent, false)
        return AlertViewHolder(view)
    }

    override fun onBindViewHolder(holder: AlertViewHolder, position: Int) {
        holder.bind(alerts[position])
    }

    override fun getItemCount(): Int = alerts.size

    inner class AlertViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val tvSeverity: TextView = itemView.findViewById(R.id.tvSeverity)
        private val tvSubstation: TextView = itemView.findViewById(R.id.tvSubstation)
        private val tvTimestamp: TextView = itemView.findViewById(R.id.tvTimestamp)
        private val tvTitle: TextView = itemView.findViewById(R.id.tvTitle)
        private val tvMessage: TextView = itemView.findViewById(R.id.tvMessage)
        private val layoutMeta: LinearLayout = itemView.findViewById(R.id.layoutMeta)
        private val tvImpact: TextView = itemView.findViewById(R.id.tvImpact)
        private val tvEta: TextView = itemView.findViewById(R.id.tvEta)

        fun bind(alert: AlertModel) {
            tvTitle.text = alert.title
            tvMessage.text = alert.message
            tvSubstation.text = alert.substation
            tvTimestamp.text = alert.timestamp

            when (alert.severity) {
                "CRITICAL" -> {
                    tvSeverity.text = "CRITICAL"
                    tvSeverity.setBackgroundResource(R.drawable.bg_badge_critical)
                    tvSeverity.setTextColor(ContextCompat.getColor(context, R.color.severity_critical_text))
                }
                "RESTORED" -> {
                    tvSeverity.text = "RESTORED"
                    tvSeverity.setBackgroundResource(R.drawable.bg_badge_restored)
                    tvSeverity.setTextColor(ContextCompat.getColor(context, R.color.severity_restored_text))
                }
                "ADVISORY" -> {
                    tvSeverity.text = "ADVISORY"
                    tvSeverity.setBackgroundResource(R.drawable.bg_badge_advisory)
                    tvSeverity.setTextColor(ContextCompat.getColor(context, R.color.severity_advisory_text))
                }
                else -> {
                    tvSeverity.text = "WARNING"
                    tvSeverity.setBackgroundResource(R.drawable.bg_badge_warning)
                    tvSeverity.setTextColor(ContextCompat.getColor(context, R.color.severity_warning_text))
                }
            }

            var hasMeta = false
            if (alert.impactCustomers > 0) {
                tvImpact.visibility = View.VISIBLE
                tvImpact.text = "👥 %,d customers".format(alert.impactCustomers)
                hasMeta = true
            } else {
                tvImpact.visibility = View.GONE
            }

            if (alert.eta.isNotEmpty()) {
                tvEta.visibility = View.VISIBLE
                tvEta.text = "⏳ ETA: ${alert.eta}"
                hasMeta = true
            } else {
                tvEta.visibility = View.GONE
            }

            layoutMeta.visibility = if (hasMeta) View.VISIBLE else View.GONE

            itemView.setOnClickListener {
                onItemClick?.invoke(alert)
            }
        }
    }
}
